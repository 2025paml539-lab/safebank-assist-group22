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

On a failure the model is shown its own rejected reply and the validator's errors and asked again, at most twice. Validity before and after this repair loop is reported in §11. [[PENDING §10.1 — the E4 validity rates (first attempt and after repair) and two validated JSON examples from the notebook run; further samples go in Appendix E.]]

## 10.2 Tools (E5)

Three simulated tools, each with a declared Pydantic input and output schema; the full specification and direct invocations are in Appendix D.

| Tool | Input | Output | Triggered by |
|---|---|---|---|
| `check_card_delivery_status` | `card_id` | `status`, `dispatched_on`, `eta_days` | `card_arrival`, `card_delivery_estimate`, `order_physical_card`, `getting_spare_card` |
| `block_card` *(destructive)* | `account_id`, `reason`: lost, stolen, compromised or damaged | `blocked`, `ref_id`, `replacement_eta_days` | `lost_or_stolen_card`, `compromised_card`, `card_swallowed` |
| `find_branch` | `pincode`, `service`: cash_deposit, atm, card_collection or identity_verification | `branch_name`, `address`, `distance_km` | `atm_support`, `cash_withdrawal_charge`, `declined_cash_withdrawal` |

Ten of the 77 intents route to a tool; the rest are answered with text only, because inventing a lookup would be a reliability risk rather than a feature. The flow is user request → LLM → validated intent → router → tool → final response. Tool arguments are validated separately from the response, so a valid response carrying nonsense arguments is caught and reported on its own. The tools are deterministic, deriving results from a hash of the input against a fixed date, so a notebook re-run gives identical output, and no real banking data or credentials are involved. `block_card` is never executed automatically (§5), and the routing metric counts that refusal as correct behaviour rather than as a missed call. [[PENDING §10.2 — one end-to-end invocation trace from the notebook's E7 run: query → validated JSON → tool call → tool result → final response.]]
