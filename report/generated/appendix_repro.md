| Item | Value |
|---|---|
| Code | https://github.com/2025paml539-lab/safebank-assist-group22 (built from commit `3a3047a`) |
| Seed | `42` for sampling, data selection and decoding |
| Final model | `Qwen/Qwen2.5-1.5B-Instruct` |
| Baseline model | `gpt2` |
| Dataset | `PolyAI/banking77`, official CSVs (Appendix G) |
| Evaluation sample | 5 per intent × 77 = 385 rows |
| Generation | max 192 new tokens; up to 2 repair attempts; escalation below confidence 0.55 |
| Application and evaluation layer | `pydantic==2.13.4`, `numpy==2.5.2`, `pandas==2.3.3`, `scikit-learn==1.9.0`, `matplotlib==3.11.1`, `torch==2.14.0` |
| Model stack (Colab) | `transformers==5.19.0`, `tokenizers==0.23.3`, `datasets==5.1.0`; torch is Colab's preinstalled build |
| Automated tests | 353 (stdlib `unittest`; 6 need real GPT-2 weights and run only with `SAFEBANK_MODEL_TESTS=1`) |
