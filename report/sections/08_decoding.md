# 8. Decoding experiments

E3 holds the model and the prompt fixed and changes only how the next token is chosen (Requirement 7). A decoding setting is a frozen `DecodeConfig`, so every row traces to an exact, printable configuration and the pipeline never knows which strategy is running. Six configurations cover the four required strategies: greedy, temperature at 0.7 and 1.2, top-k 50 [11], and top-p at 0.9 and 0.95 [12] (Appendix B). Temperature is held at 0.7 for top-k and both top-p rows, so a difference between them comes from the truncation scheme and not from the temperature.

**Protocol.** E3 ran the best E2 strategy, few-shot, on the 77-row subset in §3. Each sampled configuration ran under five seeds (42 to 46) and greedy once, because a deterministic decoder cannot vary with a seed. That is 5 × 5 × 77 + 77 = 2,002 generations, against about 10,000 for all 385 rows. **Self-consistency** follows the idea in [14] applied to the final label: for each query, the share of the five seeds that agree with its most common answer, where a reply that never became valid counts as an answer of its own. A value of 1.0 means every seed agreed. We report the mean over queries and the share of queries that were identical across all five seeds.

**Qwen's own defaults had to be neutralised.** The model ships a generation configuration with sampling on and `temperature` 0.7, `top_k` 20, `top_p` 0.8 and `repetition_penalty` 1.1. Left alone, a "temperature only" run would also have applied top-k, top-p and a repetition penalty, and every row would have meant something other than its label. `HFGenerator` resets all of them to neutral before applying a `DecodeConfig`. `top_k` has to be set to 0: `None` is refilled from the model's own configuration, which restores 20.

| Configuration | Accuracy, mean (range over seeds) | Valid, first attempt | Valid, after repair | Escalated | Agreement | Identical across seeds |
|---|---|---|---|---|---|---|
| greedy | 48.1% | 81.8% | 93.5% | 20.8% | n/a | n/a |
| temperature 0.7 | 44.7% (42.9–45.5) | 90.1% | 94.8% | 27.0% | 0.852 | 58.4% |
| temperature 1.2 | 39.5% (36.4–44.2) | 79.2% | 84.4% | 37.4% | 0.720 | 26.0% |
| top-k 50, temp 0.7 | 44.7% (42.9–45.5) | 90.4% | 94.8% | 27.0% | 0.852 | 58.4% |
| top-p 0.9, temp 0.7 | 44.9% (42.9–46.8) | 88.6% | 94.6% | 28.1% | 0.865 | 61.0% |
| top-p 0.95, temp 0.7 | 44.9% (41.6–48.1) | 87.8% | 94.8% | 27.8% | 0.862 | 59.7% |

Greedy ran once (deterministic); the other rows are means over five seeds. One query is 1.3 points of accuracy. Three sample outputs per configuration are in Appendix B.

**Sampling costs accuracy and reproducibility, and gains nothing we measured.** Greedy scored 48.1%, the same as few-shot on these 77 queries in E2. Sampling at 0.7 lost about 3 points on average (44.7% to 44.9%), two or three queries, and single seeds ranged from 41.6% to 48.1%, so the seed-to-seed spread is as large as the effect. Temperature 1.2 is clearly worse: 39.5% accuracy, final validity down to 84.4%, 37.4% of cases escalated and 1.37 generations per query. That is the reliability cost of sampling. The pipeline's default is greedy, and nothing in E3 argues for changing it.

**Top-k 50 behaved exactly like plain temperature 0.7**: the same accuracy, the same agreement, the same share of stable queries. At temperature 0.7 almost no probability lies beyond the 50 most likely tokens, so the cut-off removes nothing. The three 0.7 configurations differ in agreement by at most 0.013 (0.852 to 0.865), which five seeds and 77 queries cannot separate, so we do not claim a most stable cut-off.

**Stable is not the same as right.** At 0.7, 58% to 61% of queries get the same answer from all five seeds; at 1.2 only 26% do. But the query "How do I go about setting up an account for my daughter?" (gold `age_limit`) gets `get_disposable_virtual_card` from greedy and from most seeds, a confident and systematic error, while "How can I get the cash deposit to show up on my account?" (gold `balance_not_updated_after_cheque_or_cash_deposit`) received four different intents from five seeds under top-p 0.9, none of them correct. At temperature 0.7, 2 of 5 seeds also failed to produce a valid reply for "Is there an auto top-up option?".

**One result we did not expect.** First-attempt validity was higher under sampling at 0.7 (88% to 90%) than under greedy (81.8%). Greedy's dip is the invented-tool problem from §7; we did not test why sampling avoids it as often.

**Reproducibility.** Sampled batches are seeded once per call, so a sampled result depends on the batch it ran in; the batch size was fixed at 16 and stored with every result. For greedy we can measure the effect: the E3 greedy run and the E2 few-shot run answered the same 77 queries in differently composed batches, and 76 of 77 results were identical. The one that changed (a query about using the card for payments abroad) moved between two wrong labels, so accuracy did not change.
