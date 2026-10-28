1. Strip leading/trailing whitespace from each query (CSV reader output).
2. No lowercasing, spelling correction or deduplication: queries are kept as the customer wrote them, because noisy phrasing is part of the task.
3. Evaluation sample drawn from the TEST split only; few-shot examples drawn from the TRAIN split only, excluding any text that also appears in the evaluation sample.
4. Prompt-time normalisation (whitespace collapse, length cap) is applied later by prompts.\_clean\_query, identically for every prompt variant.
