# 11. Evaluation and results

The six criteria are implemented in `evaluate.py` and computed from the pipeline's own records on the 385-row evaluation sample. The baseline for comparison is the zero-shot prompt; the E1 models cannot produce a routable label from the simple prompt (§6), so they have no figures to compare. The final system is the few-shot prompt with greedy decoding.

| Criterion | Zero-shot (baseline) | Few-shot (final) |
|---|---|---|
| 1. Intent accuracy / macro-F1 | 40.3% / 0.362 | **47.8% / 0.450** |
| 2. Valid reply, first attempt / after repair | 95.1% / 95.3% | 83.4% / 94.8% |
| 3. Tool routing handled correctly (of 50) | 62% | 68% |
| 4. Replies flagged unsafe | 17.4% | **3.9%** |
| 5. Mean (p95) latency; generations per query | 402 ms (1,682 ms); 1.10 | 459 ms (2,058 ms); 1.22 |
| Escalated to a person | 28.1% | 21.0% |
| 6. Self-consistency (E3, 77 queries, 5 seeds) | not run | 0.85 to 0.87 at temperature 0.7; 0.72 at 1.2 |

**Accuracy.** Of the 385 queries, few-shot answered 184 correctly, 181 with a valid but wrong intent and 20 with no valid reply. The errors are a long tail (§12.1). **Validity** is analysed in §10.1: final validity is 94.8% to 95.8% for every strategy, and the repair loop fixes formatting but almost never an invented label.

**Tool routing.** Of the 50 queries whose intent should trigger a tool, 34 were handled correctly: 20 ran the right tool and 14 correctly withheld `block_card` for confirmation, which is counted as success, not as a miss (§13). No run called the wrong tool. All 16 misses and all 5 unneeded tool runs followed a wrong intent; the five unneeded runs were all `find_branch`, started when a cash-related question was labelled `cash_withdrawal_charge`. Routing is therefore not an independent source of error: it is only as good as the intent.

**Response safety.** The screen withheld 15 few-shot replies, against 65 for zero-shot; 9 of the 15 asked for a secret. None stated an invented account fact, where zero-shot had two flags that on reading were false positives (§7).

**Latency and cost.** Latency is the amortised batch time per generation on an A100, not the delay a customer would see in a one-at-a-time chat. The tail is queries that needed repair, which cost extra generations. Averaged over all 1,737 E2 generations, a prompt was 845 tokens and a completion 79.

**Confidence did nothing.** Every valid few-shot reply reported a confidence of exactly 0.9, and the other strategies used one to three values between 0.95 and 1.0. The 0.55 escalation threshold therefore never fired. Escalations came from replies withheld by the safety screen, replies still invalid after repair, `requires_human` and the destructive-action rule.
