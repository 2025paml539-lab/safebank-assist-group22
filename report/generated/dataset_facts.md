| Property | Value |
|---|---|
| Splits | train 10,003 · test 3,080 (published sizes, checked on load) |
| Fields | `text` (customer query, English) · `label` (intent id 0–76) |
| Label space | 77 intents; `validate_label_space()` passes: True |
| Train rows per intent | min 35 (`contactless_not_working`) · max 187 (`card_payment_fee_charged`) · mean 129.9 · median 127 |
| Test rows per intent | min 40 · max 40 |
| Query length (train) | median 10 words (47 characters) · mean 11.9 · 95th percentile 29 · max 79 |
| Duplicate texts | 6 appear in both train and test · 4 repeated within train |
| Evaluation sample | 385 rows from the test split, 5 per intent, 77 intents, seed 42 |
| Intents that route to a tool | 10 of 77; the rest are answered with text only |
