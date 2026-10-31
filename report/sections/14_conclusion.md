# 14. Conclusion and future work

SafeBank Assist turns a free-text banking message into a validated decision — intent, reply, optional tool call and escalation flag — using a pretrained 1.5-billion-parameter causal language model with no training. The model does the language work; deterministic code decides what is shown, which tool runs and when a person takes over. That split is what makes the system measurable: every output is either a validated record or an escalation with a stated reason.

On the 385-message sample, few-shot prompting was the only strategy that moved accuracy — 47.8% and 0.450 macro-F1, against 39.0% to 40.3% for zero-shot, role/context and constraint-based — and it also cut replies flagged unsafe from 17.4% to 3.9%, while the safety screen withheld 15 replies, 9 of them asking the customer for a secret. The repair loop raised few-shot validity from 83.4% to 94.8%, but the detail matters more than the headline: it rescued 47 of 60 formatting errors and only 1 of 62 invented labels, because showing the model its own rejected reply does not tell it which labels exist. Decoding changed little and never helped: greedy was the best setting at 48.1% on the decoding subset, sampling at temperature 0.7 cost about three points and 1.2 cost 8.6, and top-k 50 was indistinguishable from plain temperature 0.7 at every seed.

The clearest lesson so far is that a reply can pass every structural check and still be unsafe. The credential request in §12 was valid JSON with the correct intent; only a check aimed at that specific harm caught it.

**Future work.**

- **Constrained decoding:** mask the logits so only valid JSON and real labels can be generated, removing most repair calls.
- **Calibrated confidence:** derive confidence from the model's token probabilities instead of the number it writes.
- **Parameter-efficient fine-tuning:** a LoRA adapter [16] trained on the 10,003 training queries, compared directly with the best prompt.
- **Retrieval for policy questions:** RAG [15] over bank policy documents for questions the intent alone cannot answer.
- **Broader safety and real back-ends:** a learned safety classifier alongside the rules, multi-turn conversations, and authenticated tool back-ends behind a confirmation step.
