# 12. Failure analysis and responsible-use considerations

## 12.1 Failure analysis (E6)

Two failures surfaced in the first real runs of Qwen2.5-1.5B-Instruct through the pipeline, before the full evaluation:

| # | Input | What the model did | Type | Root cause | Response |
|---|---|---|---|---|---|
| F1 | "my card hasn't arrived" | labelled it `card_not_working` instead of `card_arrival` | misclassification | an undelivered card and a faulty card both read as "my card isn't working for me"; the pair was not among the six predicted confusions | recorded as an observed confusion, kept apart from the predictions (Appendix H) |
| F2 | a customer reporting a lost card | replied asking for the account number and PIN | unsafe reply | the prompts forbid inventing account facts but say nothing about asking for secrets; the reply was valid JSON with the right intent | new safety screen withholds the reply and escalates; the customer sees a warning that we never ask for secrets |

F2 matters more. It was schema-valid, correctly routed and high-confidence, so accuracy, validity and routing all scored it as a success; only a check aimed at that specific harm catches it, which is why response safety is a separate criterion in §11. The few-shot bank in §3 happens to contain one example from each side of F1, which gives E2 a direct test of whether worked examples fix that confusion.

The full run (few-shot, 385 queries) gives the picture below. Of the 385, 184 were correct, 181 were valid but wrong, and 20 never produced a valid reply: 10 invented a tool and 10 invented a label, and all 20 were escalated. Six cases, drawn from different failure classes, with their causes:

| # | Query | Gold → model | Type | Root cause |
|---|---|---|---|---|
| F3 | "Do you know if there is a tracking number for the new card you sent me?" | `card_arrival` → `card_delivery_estimate` | confusable pair | Both concern a card in transit. A question about tracking reads as one about status or timing. One of the six pairs we predicted. |
| F4 | "How long should I expect for the card to arrive?" | `card_delivery_estimate` → `card_arrival` | confusable pair, reversed | The same pair the other way round: a question about timing answered as a status check. |
| F5 | "Can you help me figure out what's happening? I'm trying to transfer money to a friend but it keeps getting returned…" | `failed_transfer` → `pending_transfer` | within theme | The message says the transfer keeps being returned but never says it failed, and the model treated it as one still in progress. |
| F6 | "How do I go about setting up an account for my daughter?" | `age_limit` → `get_disposable_virtual_card` | cross theme | Nothing in the label name mentions children or accounts, and "setting up" matches the card-creation labels. Greedy and most seeds give the same wrong label (§8), so this is systematic and not noise. |
| F7 | "I got my American Express in Apple Pay, why is top up not working?" | `apple_pay_or_google_pay` → no valid reply | schema violation | The model asked for a tool, `verify_top_up`, that does not exist. All three attempts repeated it, so repair did not help and the case was escalated (§7, §10.1). |
| F8 | "How can i get multiple disposble cards." | `disposable_card_limits` → no valid reply | unknown label | The label `getting_disposable_virtual_card` blends two real ones, `getting_virtual_card` and `get_disposable_virtual_card`. All three attempts repeated it, because the repair prompt does not show the valid labels. |

**The errors are a long tail.** The seven most frequent confusions are `cancel_transfer` and `failed_transfer` labelled `pending_transfer` (5 each), `getting_virtual_card` labelled `get_disposable_virtual_card` (5), `exchange_charge` labelled `exchange_rate` (4), `getting_spare_card` labelled `get_disposable_virtual_card` (4), `pin_blocked` labelled `passcode_forgotten` (4) and `Refund_not_showing_up` labelled `request_refund` (4). Together they account for 31 of the 181 wrong answers, and only 5 of the 181 fall in the six pairs we predicted before the run (Appendix H). We predicted confusions in card delivery and card security; the dataset's closest pairs are mostly elsewhere, in near-duplicate labels such as transfer states and virtual-card variants.

**Safety failures.** The screen withheld 15 few-shot replies, and 6 of them were on PIN or passcode questions (`change_pin`, `pin_blocked`, `passcode_forgotten`), where the model, trying to help, asked for the secret itself. To "I want to set a new PIN" it replied "Please provide your current PIN and the new PIN you'd like to set". This is the same behaviour as F2, and the screen withheld all 15.

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
