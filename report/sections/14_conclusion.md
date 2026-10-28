# 14. Conclusion and future work

SafeBank Assist turns a free-text banking message into a validated decision — intent, reply, optional tool call and escalation flag — using a pretrained 1.5-billion-parameter causal language model with no training. The model does the language work; deterministic code decides what is shown, which tool runs and when a person takes over. That split is what makes the system measurable: every output is either a validated record or an escalation with a stated reason.

[[PENDING §14 — two or three sentences summarising the measured results: the best prompt strategy and its accuracy, the effect of the repair loop on validity, the decoding finding, and what the safety screen caught.]]

The clearest lesson so far is that a reply can pass every structural check and still be unsafe. The credential request in §12 was valid JSON with the correct intent; only a check aimed at that specific harm caught it.

**Future work.**

- **Constrained decoding:** mask the logits so only valid JSON and real labels can be generated, removing most repair calls.
- **Calibrated confidence:** derive confidence from the model's token probabilities instead of the number it writes.
- **Parameter-efficient fine-tuning:** a LoRA adapter [16] trained on the 10,003 training queries, compared directly with the best prompt.
- **Retrieval for policy questions:** RAG [15] over bank policy documents for questions the intent alone cannot answer.
- **Broader safety and real back-ends:** a learned safety classifier alongside the rules, multi-turn conversations, and authenticated tool back-ends behind a confirmation step.
