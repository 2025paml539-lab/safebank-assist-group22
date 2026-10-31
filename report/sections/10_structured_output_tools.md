# 10. Structured output and tool/function calling

## 10.1 Output schema and validation (E4)

Every model reply must parse into one `AssistantResponse`, a Pydantic v2 model [18]; the full JSON Schema is in Appendix C.

| Field | Type and constraint | Purpose |
|---|---|---|
| `intent` | string; one of the 77 BANKING77 labels | the prediction |
| `confidence` | number, 0.0–1.0 | escalation signal |
| `response` | non-empty string | customer-facing reply |
| `tool_call` | `{name, args}` or null; name from a fixed list | requested lookup |
| `requires_human` | boolean, default false | model-initiated escalation |
| `disclaimer` | string, set by the application | provenance notice |

Two choices matter. The model is declared with `extra="forbid"`, so an invented field such as `"account_balance"` is a validation failure we count, not a key we silently drop. And the disclaimer is never requested from the model; the application sets it, because a provenance notice written by the model would defeat its purpose.

Raw output first passes through a brace-balanced JSON extractor that respects string literals, since models wrap JSON in prose or code fences. Validation then classifies every rejection into one of four kinds:

| Failure kind | Meaning |
|---|---|
| `no_json_found` | no balanced JSON object in the reply |
| `malformed_json` | an object was found but does not parse |
| `schema_violation` | parses, but breaks the contract: missing field, wrong type, invented field, unknown tool |
| `unknown_intent` | valid, but the label is not a BANKING77 intent — the clearest hallucination signal |

On a failure the model is shown its own rejected reply and the validator's errors and asked again, at most twice. Validity before and after this repair loop is reported in §11. In E2 the final system (few-shot) produced a valid object on the first attempt for 83.4% of the 385 queries and for 94.8% after the repair loop. Across the four strategies, first-attempt validity ranged from 83.4% to 95.1% and final validity from 94.8% to 95.8%. The table shows why first attempts failed, summed over all four strategies, and how often repair rescued them.

| First failure | zero-shot | few-shot | role / context | constraint-based | Rescued by repair |
|---|---|---|---|---|---|
| `no_json_found` | 1 | 0 | 2 | 0 | 0 of 3 |
| `malformed_json` | 1 | 0 | 2 | 0 | 3 of 3 |
| `schema_violation` | 0 | 53 | 1 | 0 | 44 of 54 |
| `unknown_intent` | 17 | 11 | 14 | 20 | 1 of 62 |

Two things stand out. Every one of the 53 few-shot schema violations was a tool name outside the three-tool enum, so the enum caught each invented tool before it could reach the router, which is the control Requirement 13 asks for. And repair fixes formatting but not labels: it rescued 47 of the 60 format failures and 1 of the 62 invented labels. The repair prompt shows the model its rejected reply and the validator's errors but does not list the valid labels, so a model that has invented a label has nothing new to choose from. Putting the catalogue into the repair prompt is the obvious next step (§13).

Two replies that passed validation on the first attempt (few-shot, raw model output):

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
  "intent": "activate_my_card",
  "confidence": 0.9,
  "response": "I can help you activate your card now. Please provide your card details so I can proceed.",
  "tool_call": null,
  "requires_human": false
}
```

Further samples, including a repaired reply and two escalations, are in Appendix E.

## 10.2 Tools (E5)

Three simulated tools, each with a declared Pydantic input and output schema; the full specification and direct invocations are in Appendix D.

| Tool | Input | Output | Triggered by |
|---|---|---|---|
| `check_card_delivery_status` | `card_id` | `status`, `dispatched_on`, `eta_days` | `card_arrival`, `card_delivery_estimate`, `order_physical_card`, `getting_spare_card` |
| `block_card` *(destructive)* | `account_id`, `reason`: lost, stolen, compromised or damaged | `blocked`, `ref_id`, `replacement_eta_days` | `lost_or_stolen_card`, `compromised_card`, `card_swallowed` |
| `find_branch` | `pincode`, `service`: cash_deposit, atm, card_collection or identity_verification | `branch_name`, `address`, `distance_km` | `atm_support`, `cash_withdrawal_charge`, `declined_cash_withdrawal` |

Ten of the 77 intents route to a tool; the rest are answered with text only, because inventing a lookup would be a reliability risk rather than a feature. The flow is user request → LLM → validated intent → router → tool → final response. Tool arguments are validated separately from the response, so a valid response carrying nonsense arguments is caught and reported on its own. The tools are deterministic, deriving results from a hash of the input against a fixed date, so a notebook re-run gives identical output, and no real banking data or credentials are involved. `block_card` is never executed automatically (§5), and the routing metric counts that refusal as correct behaviour rather than as a missed call. [[PENDING §10.2 — one end-to-end invocation trace from the notebook's E7 run: query → validated JSON → tool call → tool result → final response.]]
