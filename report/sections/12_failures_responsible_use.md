# 12. Failure analysis and responsible-use considerations

## 12.1 Failure analysis (E6)

Two failures surfaced in the first real runs of Qwen2.5-1.5B-Instruct through the pipeline, before the full evaluation:

| # | Input | What the model did | Type | Root cause | Response |
|---|---|---|---|---|---|
| F1 | "my card hasn't arrived" | labelled it `card_not_working` instead of `card_arrival` | misclassification | an undelivered card and a faulty card both read as "my card isn't working for me"; the pair was not among the six predicted confusions | recorded as an observed confusion, kept apart from the predictions (Appendix H) |
| F2 | a customer reporting a lost card | replied asking for the account number and PIN | unsafe reply | the prompts forbid inventing account facts but say nothing about asking for secrets; the reply was valid JSON with the right intent | new safety screen withholds the reply and escalates; the customer sees a warning that we never ask for secrets |

F2 matters more. It was schema-valid, correctly routed and high-confidence, so accuracy, validity and routing all scored it as a success; only a check aimed at that specific harm catches it, which is why response safety is a separate criterion in §11. The few-shot bank in §3 happens to contain one example from each side of F1, which gives E2 a direct test of whether worked examples fix that confusion.

[[PENDING §12.1 — the E6 failure table from the 385-row run: at least three analysed cases (ideally six, across validation, misclassification, routing and safety failures), each with its root cause, plus counts per failure kind and the most frequent confusions.]]

## 12.2 Responsible-use controls

Each control is implemented in code and covered by an automated test that fails if the control is removed.

| Risk | Control |
|---|---|
| Invented intent | label checked against the dataset's 77 names (`unknown_intent`) |
| Invented response field | `extra="forbid"` makes it a validation failure |
| Invented or unauthorised tool | tool name is a fixed enum; routing follows the validated intent, never the model's request |
| Irreversible action on a prediction | `block_card` never auto-executes; escalated for customer confirmation, even at confidence 1.0 |
| Reply asks for credentials | reply withheld, warning shown instead, case escalated |
| Overconfident wrong answer | confidence below 0.55 → escalate, no tool runs |
| Simulated data mistaken for real | mandatory disclaimer on every reply, including the failure path |
| Real financial data exposure | public dataset, simulated tools, synthetic identifiers only |
| Evaluation leakage | few-shot examples from the training split only, excluding every evaluation text |
| Silent failure | output still invalid after repair → escalate with a stated reason and a safe reply |

**Privacy and misuse.** The assistant never holds real account data; identifiers such as `CARD_SIM_0001` are synthetic. The credential screen addresses the most damaging misuse we observed, a support assistant teaching customers to disclose secrets, and the destructive-action rule means a misclassification cannot block a customer's card. **Reliability.** When any check fails the case goes to a person with the reason recorded, so failures are visible rather than silent. The controls are rule-based; §13 discusses their limits.
