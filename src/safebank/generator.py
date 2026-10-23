"""
Generation interface and an offline fake implementation.

This is the seam that decouples the application from the model runtime.

``TextGenerator`` is a Protocol with one method. ``pipeline.py`` depends only
on that protocol, which means:

* the whole application is testable with no torch, no transformers and no GPU;
* Vishruth's ``model_loader.py`` can land later without touching the pipeline;
* the decoding grid (E3) is just a different ``DecodeConfig``, not different code.

Owner: Kishore (architecture seam) / Vishruth (real implementation)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol, runtime_checkable

from . import config


class DecodeStrategy(str, Enum):
    """Decoding strategies compared in E3."""

    GREEDY = "greedy"
    TEMPERATURE = "temperature"
    TOP_K = "top_k"
    TOP_P = "top_p"


@dataclass(frozen=True)
class DecodeConfig:
    """
    One row of the E3 decoding grid.

    Kept as a frozen dataclass rather than loose kwargs so every generation in
    the experiments is traceable to an exact, printable configuration.
    """

    strategy: DecodeStrategy = DecodeStrategy.GREEDY
    temperature: float = 1.0
    top_k: int | None = None
    top_p: float | None = None
    max_new_tokens: int = config.MAX_NEW_TOKENS
    seed: int = config.SEED

    @property
    def do_sample(self) -> bool:
        """Greedy decoding is the only non-sampling strategy."""
        return self.strategy is not DecodeStrategy.GREEDY

    def to_generate_kwargs(self) -> dict:
        """
        Translate into Hugging Face ``model.generate`` keyword arguments.

        Only the knobs relevant to the chosen strategy are emitted, so a
        greedy run cannot accidentally carry a temperature and confuse the
        comparison table.
        """
        kwargs: dict = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": self.do_sample,
        }
        if self.strategy is DecodeStrategy.TEMPERATURE:
            kwargs["temperature"] = self.temperature
        elif self.strategy is DecodeStrategy.TOP_K:
            kwargs["temperature"] = self.temperature
            kwargs["top_k"] = self.top_k
        elif self.strategy is DecodeStrategy.TOP_P:
            kwargs["temperature"] = self.temperature
            kwargs["top_p"] = self.top_p
        return kwargs

    def label(self) -> str:
        """Short human-readable label for result tables."""
        if self.strategy is DecodeStrategy.GREEDY:
            return "greedy"
        if self.strategy is DecodeStrategy.TEMPERATURE:
            return f"temp={self.temperature}"
        if self.strategy is DecodeStrategy.TOP_K:
            return f"top_k={self.top_k} temp={self.temperature}"
        return f"top_p={self.top_p} temp={self.temperature}"

    def with_seed(self, seed: int) -> DecodeConfig:
        """Copy with a different seed, for the variability study in E3."""
        return replace(self, seed=seed)


@runtime_checkable
class TextGenerator(Protocol):
    """Anything that can turn a prompt into text under a decoding config."""

    def generate(self, prompt: str, decode: DecodeConfig) -> str:
        """Return the completion for ``prompt``, excluding the prompt itself."""
        ...


class FakeGenerator:
    """
    Scripted generator for offline development and tests.

    It returns queued completions in order, falling back to a well-formed
    default once the queue is empty. Queueing a deliberately malformed
    completion first is how we exercise the repair-retry path without a GPU.

    This is a development fixture only. Every number reported in the final
    document comes from the real model via ``model_loader.py``.
    """

    def __init__(self, scripted: list[str] | None = None, fallback: str | None = None):
        self._scripted = list(scripted or [])
        self._fallback = fallback or (
            '{"intent": "card_arrival", "confidence": 0.81, '
            '"response": "Your card is on its way. Let me check the latest status.", '
            '"tool_call": {"name": "check_card_delivery_status", '
            '"args": {"card_id": "CARD_0417"}}, "requires_human": false}'
        )
        self.calls: list[tuple[str, DecodeConfig]] = []

    def generate(self, prompt: str, decode: DecodeConfig) -> str:
        self.calls.append((prompt, decode))
        if self._scripted:
            return self._scripted.pop(0)
        return self._fallback

    @property
    def call_count(self) -> int:
        return len(self.calls)
