# 9. Adaptation strategy: prompting vs RAG vs PEFT

| Approach | Fit for SafeBank Assist | Decision |
|---|---|---|
| **Prompting with validated structured output** | The 77 labels fit in the prompt, and the task is classification plus a short reply, not knowledge recall. In-context learning [13] needs no training, and a new intent is a catalogue edit. Output is checked after generation (validation, label check, repair) rather than constrained during it. | **Chosen** |
| **Retrieval-augmented generation [15]** | There is no external corpus to retrieve from, and the whole intent catalogue already fits in context, so retrieval would add latency and a new failure mode (the wrong passage retrieved) for no gain. | Rejected; it would win if replies had to quote bank policy or a customer's history |
| **Fine-tuning / PEFT, e.g. LoRA [16]** | BANKING77 has 10,003 labelled training rows, so a LoRA adapter would likely beat prompting on accuracy, and a fine-tuned model would not need the label catalogue in every prompt (§4.2). It costs a training run, a checkpoint to version, and retraining whenever an intent is added. | Not done in this scope; the first thing to try if accuracy is the binding constraint |

Prompting was chosen because it isolates what this assignment examines — prompt design, decoding control and structured output — and because the catalogue fits in context. Whether it is also the most accurate option is an empirical question. [[PENDING §9 — one or two sentences quoting the E2 results: the best strategy's accuracy and macro-F1, and whether the remaining gap is large enough to justify PEFT.]]
