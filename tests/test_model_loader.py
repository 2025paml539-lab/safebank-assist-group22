"""
``model_loader`` without a model runtime.

What runs offline: the module imports with no torch, ``HFGenerator`` satisfies
the ``TextGenerator`` protocol, the chat-template branch, the neutral
generation config (rule 7) and stop-token counting.

Real generation needs torch + a checkpoint, so it is gated behind
``SAFEBANK_MODEL_TESTS=1`` and skipped by default. It uses GPT-2 and checks
the properties every metric depends on: completion only (no prompt echo),
deterministic greedy decoding, the context-window guard and usage records.

Owner: Vishruth
"""

from __future__ import annotations

import importlib.util
import os
import types
import unittest

from safebank.generator import DecodeConfig, DecodeStrategy, TextGenerator
from safebank.model_loader import HFGenerator, _count_until_stop

HAS_TORCH = importlib.util.find_spec("torch") is not None
RUN_MODEL_TESTS = HAS_TORCH and os.environ.get("SAFEBANK_MODEL_TESTS") == "1"


class _FakeGenConfig:
    """Mimics Qwen2.5-Instruct's shipped generation_config.json."""

    def __init__(self):
        self.do_sample = True
        self.temperature = 0.7
        self.top_k = 20
        self.top_p = 0.8
        self.min_p = None
        self.typical_p = 1.0
        self.repetition_penalty = 1.05
        self.eos_token_id = [151645, 151643]
        self.pad_token_id = None


class _FakeModel:
    def __init__(self):
        self.generation_config = _FakeGenConfig()
        self.config = types.SimpleNamespace(max_position_embeddings=1024)
        self.eval_called = False

    def parameters(self):
        yield types.SimpleNamespace(device="cpu")

    def eval(self):
        self.eval_called = True
        return self


class _FakeTokenizer:
    def __init__(self, chat_template=None):
        self.chat_template = chat_template
        self.pad_token = None
        self.eos_token = "<eos>"
        self.pad_token_id = 0
        self.padding_side = "right"
        self.truncation_side = "right"

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        return f"<user>{messages[0]['content']}</user><assistant>"


class TestOfflineContract(unittest.TestCase):
    def test_satisfies_protocol(self):
        self.assertIsInstance(HFGenerator(_FakeModel(), _FakeTokenizer()), TextGenerator)

    def test_init_applies_safety_settings(self):
        model, tok = _FakeModel(), _FakeTokenizer()
        HFGenerator(model, tok)
        self.assertTrue(model.eval_called)
        self.assertEqual(tok.pad_token, tok.eos_token)
        self.assertEqual(tok.padding_side, "left")

    def test_neutral_config_drops_shipped_sampling_defaults(self):
        model = _FakeModel()
        gen = HFGenerator(model, _FakeTokenizer())
        base = gen._base_config
        self.assertFalse(base.do_sample)
        # 0, not None: None is refilled from the model's config by generate().
        self.assertEqual(base.top_k, 0)
        self.assertEqual(base.top_p, 1.0)
        self.assertEqual(base.temperature, 1.0)
        self.assertEqual(base.repetition_penalty, 1.0)
        # The model's own config is left untouched.
        self.assertEqual(model.generation_config.top_k, 20)

    def test_chat_template_used_when_present(self):
        gen = HFGenerator(_FakeModel(), _FakeTokenizer(chat_template="{{x}}"))
        self.assertEqual(gen.format_prompt("hi"), "<user>hi</user><assistant>")

    def test_raw_prompt_without_chat_template(self):
        gen = HFGenerator(_FakeModel(), _FakeTokenizer())
        self.assertEqual(gen.format_prompt("hi"), "hi")

    def test_context_window(self):
        self.assertEqual(HFGenerator(_FakeModel(), _FakeTokenizer()).context_window, 1024)

    def test_count_until_stop(self):
        self.assertEqual(_count_until_stop([5, 6, 7, 2, 0, 0], {2, 0}), 4)
        self.assertEqual(_count_until_stop([5, 6, 7], {2}), 3)


@unittest.skipUnless(RUN_MODEL_TESTS, "set SAFEBANK_MODEL_TESTS=1 with torch installed")
class TestRealGPT2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from safebank.model_loader import load_model_and_tokenizer

        model, tok = load_model_and_tokenizer("gpt2", device="cpu")
        cls.gen = HFGenerator(model, tok)
        cls.greedy = DecodeConfig(max_new_tokens=12)

    def test_completion_excludes_prompt(self):
        prompt = "The bank told me that my card"
        out = self.gen.generate(prompt, self.greedy)
        self.assertFalse(out.startswith(prompt))

    def test_greedy_is_deterministic(self):
        prompt = "My card has not arrived and"
        self.assertEqual(
            self.gen.generate(prompt, self.greedy), self.gen.generate(prompt, self.greedy)
        )

    def test_seeded_sampling_is_reproducible(self):
        cfg = DecodeConfig(strategy=DecodeStrategy.TEMPERATURE, temperature=1.2, max_new_tokens=12)
        prompt = "Customer support said"
        self.assertEqual(self.gen.generate(prompt, cfg), self.gen.generate(prompt, cfg))

    def test_batch_matches_single_greedy(self):
        prompts = ["Hello, my card", "Why was I charged a fee for"]
        batch = self.gen.generate_batch(prompts, self.greedy)
        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0], self.gen.generate(prompts[0], self.greedy))

    def test_overlong_prompt_is_truncated_not_crashed(self):
        out = self.gen.generate("card " * 2000, self.greedy)
        self.assertIsInstance(out, str)
        self.assertTrue(self.gen.last_usage.truncated)
        self.assertLessEqual(
            self.gen.last_usage.prompt_tokens + self.greedy.max_new_tokens,
            self.gen.context_window,
        )

    def test_usage_recorded(self):
        self.gen.generate("Hello", self.greedy)
        usage = self.gen.last_usage
        self.assertGreater(usage.prompt_tokens, 0)
        self.assertLessEqual(usage.completion_tokens, self.greedy.max_new_tokens)


if __name__ == "__main__":
    unittest.main()
