Prompt template (`{query}` is replaced by the customer message):

```
Customer message: {query}
What does the customer want? Answer in one short sentence.
Answer:
```

The E1 cell, verbatim from `notebooks/safebank_colab.ipynb`:

```python
from safebank.generator import DecodeConfig
from safebank.model_loader import load_model_and_tokenizer, HFGenerator, clear_cache

E1_PROMPT = "Customer message: {query}\nWhat does the customer want? Answer in one short sentence.\nAnswer:"
e1_rows = eval_rows[::77][:5]          # 5 different intents, fixed by the seed
greedy = DecodeConfig(max_new_tokens=48)

def run_e1(model_id):
    gen = HFGenerator(*load_model_and_tokenizer(model_id))
    outs = [gen.generate(E1_PROMPT.format(query=r["query"]), greedy) for r in e1_rows]
    return outs, gen.usage_log

gpt2_out, gpt2_usage = run_e1(config.BASELINE_MODEL_ID)
clear_cache()
qwen_out, qwen_usage = run_e1(config.MODEL_ID)

e1 = pd.DataFrame({
    "query": [r["query"] for r in e1_rows],
    "gold_intent": [r["gold_intent"] for r in e1_rows],
    "gpt2": gpt2_out,
    "qwen2.5-1.5b-instruct": qwen_out,
    "gpt2_ms": [u.latency_ms for u in gpt2_usage],
    "qwen_ms": [u.latency_ms for u in qwen_usage],
})
e1.to_csv(config.RESULTS_DIR / "e1_baseline.csv", index=False)
pd.set_option("display.max_colwidth", 120)
e1
```
