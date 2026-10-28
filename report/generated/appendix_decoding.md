| Configuration | generate() arguments | Rationale |
|---|---|---|
| `greedy` | `max_new_tokens=192, do_sample=False` | Deterministic argmax decoding. The reproducible reference point for E3 and the fixed baseline for the self-consistency study, since its output cannot vary across seeds. |
| `temperature=0.7` | `max_new_tokens=192, do_sample=True, temperature=0.7` | Moderate-temperature sampling. Introduces controlled variety while keeping the distribution close to the model's argmax; the honest middle ground between greedy and hot sampling. |
| `temperature=1.2` | `max_new_tokens=192, do_sample=True, temperature=1.2` | High-temperature sampling. Flattens the distribution to expose the reliability cost of sampling: expected to raise output variability and lower intent accuracy versus the moderate setting, isolating temperature's own effect. |
| `top_k=50 temp=0.7` | `max_new_tokens=192, do_sample=True, temperature=0.7, top_k=50` | Top-k truncation: sample only from the k most probable tokens. Caps the long tail with a fixed-size candidate set; compared against top-p at the same temperature so the difference is the truncation scheme, not the temperature. |
| `top_p=0.9 temp=0.7` | `max_new_tokens=192, do_sample=True, temperature=0.7, top_p=0.9` | Nucleus (top-p) truncation: sample from the smallest set whose cumulative probability reaches p. Adapts the candidate-set size to the model's certainty, unlike the fixed k of top-k. |
| `top_p=0.95 temp=0.7` | `max_new_tokens=192, do_sample=True, temperature=0.7, top_p=0.95` | A looser nucleus than the 0.9 config, admitting more of the tail. Shows how sensitive top-p behaviour is to the p cutoff while holding the strategy and temperature fixed. |

Seeds for the self-consistency study: 42, 43, 44, 45, 46. Greedy decoding is deterministic, so it contributes a single run.
