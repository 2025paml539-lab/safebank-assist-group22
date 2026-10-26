"""
Real model loading and the Hugging Face ``TextGenerator``.

``HFGenerator`` is the production implementation of ``generator.TextGenerator``:
swapping it in for ``FakeGenerator`` is the only change needed to turn the
offline pipeline into the real E1/E2/E3/E7 runs.

Correctness rules this module enforces (see WORKLOG.md section 5.2)
-------------------------------------------------------------------
1. Returns the completion ONLY; the prompt tokens are sliced off before
   decoding, so a prompt echo can never be scored as a model failure.
2. ``pad_token`` falls back to ``eos_token`` (GPT-2 has none), with left
   padding so batched decoder-only generation lines prompts up at the end.
3. ``model.eval()`` on load, and generation under ``torch.inference_mode``.
4. Decoding knobs come only from ``DecodeConfig.to_generate_kwargs()``.
5. ``transformers.set_seed(decode.seed)`` immediately before every sampled
   generation.
6. Chat template for instruction-tuned models; plain text for GPT-2, which
   has none (``tokenizer.chat_template is None``).

Two further rules found while testing against the real checkpoints:

7. Neutral generation defaults. ``Qwen2.5-Instruct`` ships a
   ``generation_config.json`` with ``top_k=20, top_p=0.8, temperature=0.7,
   repetition_penalty=1.05``, and stock ``GenerationConfig`` defaults to
   ``top_k=50``. Either would silently leak into every E3 configuration (a
   "temperature only" run would really be temperature + top-k + top-p).
   Each call therefore starts from a neutral config, so only the knobs the
   ``DecodeConfig`` names are active.
8. Context-window guard. GPT-2 has 1024 positions; the few-shot prompt is
   ~1,600 tokens. Prompts that would overflow are truncated from the LEFT
   (the instructions), keeping the customer query at the end, and the
   truncation is recorded in :class:`GenerationUsage`.

``torch`` and ``transformers`` are imported inside function bodies only, so
``import safebank`` and the offline test suite never need them.

Owner: Vishruth (framework, environment, reproducibility)
"""

from __future__ import annotations

import copy
import time
from dataclasses import asdict, dataclass

from . import config
from .generator import DecodeConfig

# --------------------------------------------------------------------------
# Hardware + versions, for the reproducibility appendix
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceReport:
    """Hardware and library facts quoted in the reproducibility appendix."""

    device: str
    device_name: str
    cuda_capability: tuple[int, int] | None
    vram_gb: float | None
    torch_version: str
    transformers_version: str
    cuda_version: str | None
    dtype: str

    def as_dict(self) -> dict:
        return asdict(self)


def _resolve_device(device: str | None) -> str:
    import torch

    if device:
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_dtype(device: str, dtype: str) -> str:
    # fp16 matmuls are unsupported or very slow on CPU; fall back to fp32 there.
    return "float32" if device == "cpu" and dtype == "float16" else dtype


def device_report(device: str | None = None, dtype: str = "float16") -> DeviceReport:
    """Collect device, GPU capability, VRAM, library versions and dtype."""
    import platform

    import torch
    import transformers

    device = _resolve_device(device)
    on_cuda = device.startswith("cuda") and torch.cuda.is_available()
    return DeviceReport(
        device=device,
        device_name=torch.cuda.get_device_name(0) if on_cuda else platform.processor() or "cpu",
        cuda_capability=tuple(torch.cuda.get_device_capability(0)) if on_cuda else None,
        vram_gb=(
            round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
            if on_cuda
            else None
        ),
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        cuda_version=torch.version.cuda,
        dtype=_resolve_dtype(device, dtype),
    )


# --------------------------------------------------------------------------
# Loading, cached at module level
# --------------------------------------------------------------------------

#: (model_id, device, dtype) -> (model, tokenizer). Reloading a 3 GB checkpoint
#: per experiment would make the notebook unusable on a T4.
_CACHE: dict[tuple[str, str, str], tuple[object, object]] = {}


def load_model_and_tokenizer(
    model_id: str = config.MODEL_ID,
    *,
    device: str | None = None,
    dtype: str = "float16",
    cache_dir: str | None = None,
) -> tuple[object, object]:
    """
    Load a pretrained causal LM and its tokenizer. Returns ``(model, tokenizer)``.

    The pair is cached per ``(model_id, device, dtype)``, so calling this again
    in a later notebook cell is free.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = _resolve_device(device)
    dtype = _resolve_dtype(device, dtype)
    key = (model_id, device, dtype)
    if key in _CACHE:
        return _CACHE[key]

    tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir=cache_dir)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    tokenizer.truncation_side = "left"

    model = AutoModelForCausalLM.from_pretrained(
        model_id, dtype=getattr(torch, dtype), cache_dir=cache_dir
    )
    model.to(device)
    model.eval()

    _CACHE[key] = (model, tokenizer)
    return model, tokenizer


def clear_cache() -> None:
    """Drop cached models, e.g. before loading Qwen after the GPT-2 baseline."""
    _CACHE.clear()
    try:
        import gc

        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


# --------------------------------------------------------------------------
# The real TextGenerator
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationUsage:
    """Per-generation cost record, for evaluation criterion 5."""

    prompt_tokens: int
    completion_tokens: int
    truncated: bool
    latency_ms: float
    batch_size: int


class HFGenerator:
    """
    ``TextGenerator`` backed by a Hugging Face causal LM.

    Satisfies ``generator.TextGenerator`` structurally. ``generate`` serves the
    pipeline one prompt at a time; ``generate_batch`` is the fast path for the
    E2/E3 sweeps on a T4.

    Every call appends one :class:`GenerationUsage` per prompt to
    ``usage_log``. With batching, ``latency_ms`` is the batch wall time
    divided by the batch size.
    """

    def __init__(
        self,
        model,
        tokenizer,
        *,
        device: str | None = None,
        use_chat_template: bool | None = None,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or str(next(model.parameters()).device)
        self.use_chat_template = (
            tokenizer.chat_template is not None
            if use_chat_template is None
            else use_chat_template
        )
        self.usage_log: list[GenerationUsage] = []
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"
        self.tokenizer.truncation_side = "left"
        self.model.eval()
        self._base_config = self._neutral_generation_config()

    # -- configuration ---------------------------------------------------

    def _neutral_generation_config(self):
        """Copy of the model's config with every sampling knob made inert (rule 7)."""
        gc = copy.deepcopy(self.model.generation_config)
        gc.do_sample = False
        gc.temperature = 1.0
        gc.top_k = None
        gc.top_p = 1.0
        gc.min_p = None
        gc.typical_p = 1.0
        gc.repetition_penalty = 1.0
        gc.pad_token_id = self.tokenizer.pad_token_id
        return gc

    @property
    def context_window(self) -> int:
        cfg = self.model.config
        return int(
            getattr(cfg, "max_position_embeddings", None)
            or getattr(cfg, "n_positions", None)
            or 2048
        )

    @property
    def last_usage(self) -> GenerationUsage | None:
        return self.usage_log[-1] if self.usage_log else None

    # -- prompting -------------------------------------------------------

    def format_prompt(self, prompt: str) -> str:
        """Wrap in the chat template for instruct models; GPT-2 gets raw text."""
        if not self.use_chat_template:
            return prompt
        return self.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
        )

    # -- generation ------------------------------------------------------

    def generate(self, prompt: str, decode: DecodeConfig) -> str:
        """Return the completion for ``prompt``, excluding the prompt itself."""
        return self.generate_batch([prompt], decode)[0]

    def generate_batch(self, prompts: list[str], decode: DecodeConfig) -> list[str]:
        """
        Generate completions for several prompts in one forward pass.

        Sampled batches are seeded once per call, so a sampled result depends
        on the batch it ran in. Keep the batch size fixed within an
        experiment (the notebook does) and record it alongside the results.
        """
        import torch
        import transformers

        if not prompts:
            return []

        texts = [self.format_prompt(p) for p in prompts]
        max_prompt = max(1, self.context_window - decode.max_new_tokens)
        untruncated = self.tokenizer(texts, padding=True, return_tensors="pt")
        truncated = untruncated["input_ids"].shape[1] > max_prompt
        enc = (
            self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=max_prompt,
                return_tensors="pt",
            )
            if truncated
            else untruncated
        ).to(self.device)

        gen_config = copy.deepcopy(self._base_config)
        gen_config.update(**decode.to_generate_kwargs())

        if decode.do_sample:
            transformers.set_seed(decode.seed)

        started = time.perf_counter()
        with torch.inference_mode():
            out = self.model.generate(**enc, generation_config=gen_config)
        elapsed_ms = (time.perf_counter() - started) * 1000

        # Left padding: every prompt ends at the same column, so slicing at
        # the input width leaves exactly the newly generated tokens (rule 1).
        new_tokens = out[:, enc["input_ids"].shape[1] :]
        completions = self.tokenizer.batch_decode(new_tokens, skip_special_tokens=True)

        prompt_lens = enc["attention_mask"].sum(dim=1).tolist()
        stop_ids = self._stop_token_ids()
        per_item_ms = elapsed_ms / len(prompts)
        for row, n_prompt in zip(new_tokens.tolist(), prompt_lens):
            self.usage_log.append(
                GenerationUsage(
                    prompt_tokens=int(n_prompt),
                    completion_tokens=_count_until_stop(row, stop_ids),
                    truncated=truncated,
                    latency_ms=round(per_item_ms, 1),
                    batch_size=len(prompts),
                )
            )
        return [c.strip() for c in completions]

    def _stop_token_ids(self) -> set[int]:
        eos = self._base_config.eos_token_id
        ids = set(eos if isinstance(eos, (list, tuple)) else [eos])
        ids.add(self.tokenizer.pad_token_id)
        ids.discard(None)
        return ids


def _count_until_stop(token_ids: list[int], stop_ids: set[int]) -> int:
    """Generated tokens up to and including the first stop token; padding excluded."""
    for i, tok in enumerate(token_ids):
        if tok in stop_ids:
            return i + 1
    return len(token_ids)
