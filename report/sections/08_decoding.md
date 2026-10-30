# 8. Decoding experiments

E3 holds the model and the prompt fixed and changes only how the next token is chosen (Requirement 7). The pipeline never knows which strategy is running: a decoding setting is a frozen `DecodeConfig`, so every row in the results is traceable to an exact, printable configuration, and a greedy run cannot carry a stray temperature. Six configurations cover the four required strategies (Appendix B):

| Configuration | Strategy | Temperature | Cut-off | Why it is in the grid |
|---|---|---|---|---|
| greedy | argmax | n/a | n/a | the deterministic reference; the baseline for the stability measurement |
| temperature = 0.7 | sampling | 0.7 | none | moderate variety, close to the model's argmax |
| temperature = 1.2 | sampling | 1.2 | none | flattens the distribution to expose the reliability cost of sampling; separates temperature's own effect |
| top-k = 50 | sampling [11] | 0.7 | k = 50 | caps the tail at a fixed number of candidates |
| top-p = 0.9 | sampling [12] | 0.7 | nucleus mass 0.9 | candidate set grows and shrinks with the model's certainty |
| top-p = 0.95 | sampling [12] | 0.7 | nucleus mass 0.95 | a looser nucleus, to show how sensitive top-p is to its cut-off |

Temperature is held at 0.7 for top-k and both top-p rows, so a difference between them comes from the truncation scheme and not from the temperature. Temperature appears at 0.7 and 1.2 for the same reason, in the other direction.

**Protocol.** E3 runs the best strategy from E2 (§7) over the 77-row subset in §3, one query per intent. Each sampled configuration is run under five seeds (42 to 46) and greedy once, because a deterministic decoder cannot vary with a seed and reporting five identical runs would suggest a measurement that does not exist. That is 5 × 5 × 77 + 77 = 2,002 generations; on all 385 rows it would be about 10,000. Each run is seeded immediately before generation. Each row of the results table reports accuracy (mean, minimum and maximum across seeds), schema validity before and after repair, escalation rate and mean attempts. **Self-consistency** follows the idea in [14] applied to the final label: for each query, the share of the five seeds that agree with its most common prediction. A value of 1.0 means every seed gave the same intent; we report the mean over queries and the fraction of queries that were fully stable.

**Qwen's own defaults had to be neutralised.** The model ships a generation configuration with sampling on and `temperature` 0.7, `top_k` 20, `top_p` 0.8 and `repetition_penalty` 1.1. Left alone, a "temperature only" run would also have applied top-k, top-p and a repetition penalty, and every row would have meant something other than its label. `HFGenerator` resets all of them to neutral before applying a `DecodeConfig`. One reset needed a second pass: setting `top_k` to `None` does not disable it, because `generate()` fills unset fields back in from the model's own configuration and restores `top_k` 20; it has to be set to 0. Without that, the temperature and top-p rows would have carried an unlabelled top-k cut-off.

**Reproducibility.** Sampled batches are seeded once per call, so a sampled result depends on the batch it ran in. The batch size is fixed at 16 across E2 and E3 and stored in every result file. Greedy output can also differ very slightly between batched and unbatched runs, because padding changes floating-point accumulation; §13 lists this as a limitation.

[[PENDING §8 — the E3 table from `experiments.GridResult.summary` (one row per configuration), three sample outputs per configuration from `experiments.sample_outputs`, and two or three queries where the seeds disagree from `experiments.variability_examples`. Then the reading: does sampling lower accuracy or validity compared with greedy, which cut-off is most stable, and does temperature 1.2 show the reliability cost of sampling.]]
