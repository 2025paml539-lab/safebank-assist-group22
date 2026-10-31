<div class="newpage"></div>

# Appendix

## A. Prompt experiment log

### A.1 Baseline prompt (E1)

<!-- include: generated/appendix_e1.md -->

### A.2 The four prompt strategies (E2)

<!-- include: generated/appendix_prompts.md -->

## B. Decoding configurations (E3)

<!-- include: generated/appendix_decoding.md -->

**Sample outputs.** The first three of the 77 queries under every configuration (seed 42 for the sampled ones), as the model replied after validation and repair. "No valid reply" means all three attempts failed validation and the case was escalated.

| Configuration | Query | Intent | Reply |
|---|---|---|---|
| greedy | I need to activate my card can you do that now? | `activate_my_card` | I can help you activate your card now. Please provide your card details so I… |
| greedy | How do I go about setting up an account for my daug… | `get_disposable_virtual_card` | I can help you with that. Let me guide you through the process of setting up… |
| greedy | Can I use the system Google Pay for top-ups? | `apple_pay_or_google_pay` | Yes, you can use Google Pay for top-ups. Would you like to proceed with this… |
| temperature=0.7 | I need to activate my card can you do that now? | `activate_my_card` | I can help with that. Please follow the prompts to activate your card. |
| temperature=0.7 | How do I go about setting up an account for my daug… | `get_disposable_virtual_card` | I can guide you through setting up a disposable virtual card for your daughte… |
| temperature=0.7 | Can I use the system Google Pay for top-ups? | `apple_pay_or_google_pay` | I can help you with that. Google Pay can be used for top-ups on your card. |
| temperature=1.2 | I need to activate my card can you do that now? | `activate_my_card` | Sure, I can guide you through the process. Let's initiate the activation of y… |
| temperature=1.2 | How do I go about setting up an account for my daug… | `no valid reply` | (none) |
| temperature=1.2 | Can I use the system Google Pay for top-ups? | `apple_pay_or_google_pay` | I can help you with that. Currently, Google Pay is not enabled for top-ups wh… |
| top_k=50 temp=0.7 | I need to activate my card can you do that now? | `activate_my_card` | I can help with that. Please follow the prompts to activate your card. |
| top_k=50 temp=0.7 | How do I go about setting up an account for my daug… | `get_disposable_virtual_card` | I can guide you through setting up a disposable virtual card for your daughte… |
| top_k=50 temp=0.7 | Can I use the system Google Pay for top-ups? | `apple_pay_or_google_pay` | I can help you with that. Google Pay can be used for top-ups on your card. |
| top_p=0.9 temp=0.7 | I need to activate my card can you do that now? | `activate_my_card` | I can help with that. Please provide your card details so I can activate it f… |
| top_p=0.9 temp=0.7 | How do I go about setting up an account for my daug… | `get_disposable_virtual_card` | I can guide you through setting up a disposable virtual card for your daughte… |
| top_p=0.9 temp=0.7 | Can I use the system Google Pay for top-ups? | `apple_pay_or_google_pay` | I can help you with that. Google Pay can be used for top-ups on your card. |
| top_p=0.95 temp=0.7 | I need to activate my card can you do that now? | `activate_my_card` | I can help with that. Please follow the prompts to activate your card. |
| top_p=0.95 temp=0.7 | How do I go about setting up an account for my daug… | `get_disposable_virtual_card` | I can guide you through setting up a disposable virtual card for your daughte… |
| top_p=0.95 temp=0.7 | Can I use the system Google Pay for top-ups? | `apple_pay_or_google_pay` | I can help you with that. Google Pay can be used for top-ups on your card. |


## C. Structured-output schema (E4)

<!-- include: generated/appendix_schema.md -->

## D. Tool specifications and invocations (E5)

<!-- include: generated/appendix_tools.md -->

## E. Sample validated outputs

All samples are from the few-shot run on the 385-row evaluation sample (`artifacts/results/e2_few_shot.json`). Each shows the model's raw first reply and the `to_row()` record the evaluation reads. `response` is the model's own reply, before the application adds the system-lookup trace and the disclaimer.

**E.1 Valid, with a tool call.** The intent is right and `find_branch` ran.

Query: "Which ATMs accept this card?" (gold intent `atm_support`)

```json
{
  "intent": "atm_support",
  "confidence": 0.9,
  "response": "I can help with that. Let me find the nearest branch or ATM for you.",
  "tool_call": {"name": "find_branch", "args": {"pincode": "560001", "service": "atm"}},
  "requires_human": false
}
```

```json
{
  "query": "Which ATMs accept this card?",
  "ok": true,
  "intent": "atm_support",
  "confidence": 0.9,
  "response": "I can help with that. Let me find the nearest branch or ATM for you.",
  "attempts": 1,
  "needed_repair": false,
  "first_failure": null,
  "tool": "find_branch",
  "tool_ok": true,
  "escalated": false,
  "safety_issues": "",
  "reply_withheld": false,
  "latency_ms": 209.5
}
```

**E.2 Valid, with a tool call.** A delivery lookup ran.

Query: "When will I get my card?" (gold intent `card_arrival`)

```json
{
  "intent": "card_arrival",
  "confidence": 0.9,
  "response": "I can help with that. Let me check the delivery status of your card.",
  "tool_call": {"name": "check_card_delivery_status", "args": {"card_id": "CARD_SIM_0001"}},
  "requires_human": false
}
```

```json
{
  "query": "When will I get my card?",
  "ok": true,
  "intent": "card_arrival",
  "confidence": 0.9,
  "response": "I can help with that. Let me check the delivery status of your card.",
  "attempts": 1,
  "needed_repair": false,
  "first_failure": null,
  "tool": "check_card_delivery_status",
  "tool_ok": true,
  "escalated": false,
  "safety_issues": "",
  "reply_withheld": false,
  "latency_ms": 168.0
}
```

**E.3 Valid, text only.** No tool is needed for this intent.

Query: "I need to activate my card can you do that now?" (gold intent `activate_my_card`)

```json
{
  "intent": "activate_my_card",
  "confidence": 0.9,
  "response": "I can help you activate your card now. Please provide your card details so I can proceed.",
  "tool_call": null,
  "requires_human": false
}
```

```json
{
  "query": "I need to activate my card can you do that now?",
  "ok": true,
  "intent": "activate_my_card",
  "confidence": 0.9,
  "response": "I can help you activate your card now. Please provide your card details so I can proceed.",
  "attempts": 1,
  "needed_repair": false,
  "first_failure": null,
  "tool": null,
  "tool_ok": null,
  "escalated": false,
  "safety_issues": "",
  "reply_withheld": false,
  "latency_ms": 209.8
}
```

**E.4 Needed repair.** The first reply invented a tool, `verify_my_identity`, so validation rejected it. The model was shown its reply and the error and asked again.

Query: "What age do my kids need to be to use your service?" (gold intent `age_limit`)

First reply (rejected):

```json
{
  "intent": "age_limit",
  "confidence": 0.9,
  "response": "I can help with that. Let me find the minimum age requirement for using our service.",
  "tool_call": {"name": "verify_my_identity", "args": {"service": "kids_service"}},
  "requires_human": false
}
```

Validator errors: `tool_call.name: Input should be 'check_card_delivery_status', 'block_card' or 'find_branch'`

Repaired reply (accepted):

```json
{
  "intent": "age_limit",
  "confidence": 0.9,
  "response": "I can help with that. Let me find the minimum age requirement for using our service.",
  "tool_call": null,
  "requires_human": false
}
```

```json
{
  "query": "What age do my kids need to be to use your service?",
  "ok": true,
  "intent": "age_limit",
  "confidence": 0.9,
  "response": "I can help with that. Let me find the minimum age requirement for using our service.",
  "attempts": 2,
  "needed_repair": true,
  "first_failure": "schema_violation",
  "tool": null,
  "tool_ok": null,
  "escalated": false,
  "safety_issues": "",
  "reply_withheld": false,
  "latency_ms": 1298.9
}
```

**E.5 Escalated: destructive action withheld.** The intent is right, but `block_card` changes the account, so no tool ran and the case went to a person for confirmation (`tool` is null, `escalated` is true).

Query: "The ATM didn't give me the card back!" (gold intent `card_swallowed`)

```json
{
  "intent": "card_swallowed",
  "confidence": 0.9,
  "response": "I'm sorry to hear that. We'll need to block your card to prevent any further issues. A colleague will confirm this with you.",
  "tool_call": null,
  "requires_human": true
}
```

```json
{
  "query": "The ATM didn't give me the card back!",
  "ok": true,
  "intent": "card_swallowed",
  "confidence": 0.9,
  "response": "I'm sorry to hear that. We'll need to block your card to prevent any further issues. A colleague will confirm this with you.",
  "attempts": 1,
  "needed_repair": false,
  "first_failure": null,
  "tool": null,
  "tool_ok": null,
  "escalated": true,
  "safety_issues": "",
  "reply_withheld": false,
  "latency_ms": 141.7
}
```

**E.6 Escalated: reply withheld by the safety screen.** The reply asks the customer for a card number, so it was withheld and the customer sees a warning instead. The intent here is also wrong.

Query: "Please put a freeze on my card,  I am worried there has been some payments on it and I don't know what for." (gold intent `card_payment_not_recognised`)

```json
{
  "intent": "compromised_card",
  "confidence": 0.9,
  "response": "I understand your concern. I will put a freeze on your card to prevent any unauthorized transactions. Please provide your account number and PIN so I can proceed with the freeze.",
  "tool_call": null,
  "requires_human": false
}
```

```json
{
  "query": "Please put a freeze on my card,  I am worried there has been some payments on it and I don't know what for.",
  "ok": true,
  "intent": "compromised_card",
  "confidence": 0.9,
  "response": "I understand your concern. I will put a freeze on your card to prevent any unauthorized transactions. Please provide your account number and PIN so I can proceed with the freeze.",
  "attempts": 1,
  "needed_repair": false,
  "first_failure": null,
  "tool": null,
  "tool_ok": null,
  "escalated": true,
  "safety_issues": "credential_solicitation",
  "reply_withheld": true,
  "latency_ms": 141.7
}
```


## F. Reproducibility

<!-- include: generated/appendix_repro.md -->

The block above lists the project's pinned versions. The runs used the hardware and libraries below, taken from `device_report()` as saved with each run. E1 and the E7 smoke run ran on a free Colab T4; E2, E3 and E6 ran on a Kubeflow JupyterLab server with an NVIDIA A100, because the newer torch build on the T4 needs a CUDA 13 driver that the server does not have.

| Item | E1 and E7 (Colab) | E2, E3 and E6 (Kubeflow server) |
|---|---|---|
| GPU | Tesla T4 | NVIDIA A100-SXM4-80GB |
| CUDA capability | 7.5 | 8.0 |
| GPU memory | 14.6 GB | 79.2 GB |
| torch | 2.11.0+cu130 | 2.8.0+cu128 |
| transformers | 5.19.0 | 5.19.0 |
| CUDA | 13.0 | 12.8 |
| dtype | float16 | float16 |
| Python | not recorded | 3.11.11 |
| Batch size | see section 6 | 16 (first attempts batched; repair prompts one at a time) |
| Code | commit shown above | fork branch at commit `e7b1334`, merged into `main` with the results |

Numeric results can differ slightly between these two setups, because the torch builds differ and batched greedy decoding can differ from one-at-a-time decoding in rare cases (§13). Neither affects the comparisons within E2 or within E3, which each ran in a single setup.

Other libraries installed on the E2, E3 and E6 server, which differ from the pins above: `numpy` 2.3.5 (the pinned 2.5.2 does not exist for Python 3.11), `pandas` 3.1.0, `scikit-learn` 1.9.1, `pydantic` 2.14.2 with `pydantic_core` 2.50.2, `huggingface_hub` 2.4.0, `brotli` 1.2.1, `torchvision` 0.23.0 and `torchaudio` 2.8.0. The image shipped torch 2.5.1 and NumPy 1.26.4; torch was upgraded to 2.8.0 because `transformers` 5.19.0 needs `torch.accelerator` (torch 2.6 or newer), and NumPy to 2.3.5 because the `pyarrow` that `datasets` 5.1.0 requires needs NumPy 2. The server could not reach `raw.githubusercontent.com`, so the two official BANKING77 CSVs were copied in from the PolyAI repository through `github.com`; the 385 evaluation rows rebuilt from them were identical to the frozen sample in `artifacts/results/eval_sample.jsonl`, checked in the same session.

## G. Dataset preprocessing record

<!-- include: generated/preprocessing_record.md -->

## H. Failure-analysis focus set

<!-- include: generated/focus_themes.md -->

<!-- include: generated/appendix_focus.md -->

## I. Individual contribution statement

<!-- include: contribution_statement.md -->
