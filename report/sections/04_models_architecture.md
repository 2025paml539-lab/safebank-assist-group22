# 4. Generative-model and LLM architecture analysis

## 4.1 Generative-model families

A generative model learns the distribution of its training data and then draws new samples from it. Four families differ in what they learn, how a sample is produced, and how well they suit discrete text:

| Family | What it learns | How a sample is produced | Discrete text | Conditioning |
|---|---|---|---|---|
| **GAN** [19] | A generator that maps random noise to a sample, trained against a discriminator that tries to tell real from generated. The data distribution is implicit; there is no likelihood. | One forward pass of the generator on noise. | Poor fit. Choosing a token is a discrete step with no gradient, so the discriminator's signal cannot reach the generator directly. | Feed a label or other condition to both networks. |
| **VAE** [20] | An encoder that maps data to a distribution over a latent code, and a decoder that rebuilds the data from it. Trained on a bound that combines reconstruction error with a penalty keeping the latent code close to a simple prior. | Draw a latent code from the prior and decode it. | Possible with a sequence decoder, but the decoder can learn to ignore the latent code, so control over the output is weak. | Feed a condition to the encoder and decoder. |
| **Diffusion** [21] | A network that undoes a fixed, gradual noising process, one small step at a time. | Start from pure noise and denoise over many steps (1,000 in the original model). | Built for continuous data such as images. Text needs adaptations, such as diffusing in embedding space. | Pass the condition into the denoising network. |
| **Autoregressive LM** [3] | The distribution of the next token given all previous tokens; the probability of a whole sequence is the product of these conditionals (§4.2). | Generate one token at a time, each conditioned on the tokens so far, until an end token or a length limit. | Native. The vocabulary is discrete and the model outputs a probability over it. | Put the condition in the prompt as text. |

A causal LM fits SafeBank Assist for four reasons. The output we need is discrete: an intent label from a fixed list of 77, a reply, and a JSON object, all of which are token sequences. The input is an arbitrary customer message, and a prompt can carry it together with the label catalogue, the tool catalogue, the schema and worked examples, so a new intent is a catalogue edit and not a retraining run. An instruction-tuned model [10] follows those instructions directly, which is what lets one pass produce the label, the reply and the tool request. And sampling from a next-token distribution gives the decoding controls compared in §8: greedy, temperature, top-k [11] and top-p [12].

The cost is that nothing in the model guarantees a valid object, and nothing stops it writing a plausible label that does not exist. That is why the application validates every reply after generation, repairs it once or twice, and escalates when that fails (§10).

## 4.2 LLM architecture and autoregressive generation

Both models we use are decoder-only causal language models [2, 3, 4]. Given the tokens so far, the model outputs a probability distribution over the next token, and the probability of a whole sequence factorises into those conditionals:

<p class="eq"><img src="../assets/eq_factorisation.svg" alt="p(x1..xT) = product over t of p(x_t | x_<t)"></p>

Pretraining fits this by minimising next-token cross-entropy; instruction tuning [10] continues with the same objective on prompt–response pairs. We use the published checkpoints as they are. Everything SafeBank Assist does — classify, reply, request a tool, emit JSON — is this one prediction applied repeatedly. Table 1 compares the two checkpoints; every figure was checked against their published configuration files [22], and the Qwen parameter counts match its model card.

<p class="caption">Table 1. The two checkpoints.</p>

| | GPT-2 (E1 baseline) | Qwen2.5-1.5B-Instruct (final system) |
|---|---|---|
| Parameters | 124.4 M | 1.54 B (1.31 B excluding embeddings) |
| Decoder blocks · hidden size | 12 · 768 | 28 · 1,536 |
| Attention heads | 12, each with its own keys and values | 12 query heads sharing 2 key/value heads (GQA [7]) |
| Feed-forward | 768 → 3,072 → 768, GELU | 1,536 → 8,960 → 1,536, SwiGLU [8] |
| Normalisation · positions | LayerNorm · learned, 1,024 slots | RMSNorm [9] · rotary (RoPE [6]), 32,768 positions |
| Tokenizer | byte-level BPE [5], 50,257 tokens | byte-level BPE, 151,643 tokens + 22 special |
| Instruction-tuned · chat format | no · none | yes · ChatML role markers |
| Weights in fp16 | ≈ 0.25 GB | ≈ 3.1 GB |

**Tokenization.** Both tokenizers use byte-level byte-pair encoding [5]: text is split into UTF-8 bytes and frequent byte sequences are merged into single tokens. Every byte has a token, so a misspelt query never fails as out-of-vocabulary; a rare word just becomes more pieces. Token count sets three practical limits. Each request re-processes the whole prompt, about 750 tokens for Qwen and mostly the 77-label catalogue, against at most 192 generated tokens. GPT-2 has exactly 1,024 position slots while the few-shot prompt is about 1,600 tokens, so GPT-2 only ever sees a truncated version of it. And Qwen wraps the prompt in ChatML role markers; when no system message is given its template inserts a default one (*"You are Qwen, created by Alibaba Cloud. You are a helpful assistant."*), so every Qwen prompt carries that hidden turn. It is the same for all four prompt variants, so comparisons between them stay fair.

**Tokenizer walkthrough.** Qwen's tokenizer on one evaluation query, from the notebook run (Appendix F). The 47 characters of *"I need to activate my card can you do that now?"* become 12 token ids — 40, 1184, 311, 20276, 847, 3701, 646, 498, 653, 429, 1431, 30 — which decode to `I`, `·need`, `·to`, `·activate`, `·my`, `·card`, `·can`, `·you`, `·do`, `·that`, `·now`, `?`, where `·` is the leading space the token keeps. Every word here is a single token, about 3.9 characters each; a rarer or misspelt word splits into more pieces instead of failing. The same cell reports the loaded checkpoint's own dimensions — vocabulary 151,643, hidden size 1,536, 28 decoder blocks, 12 attention heads, 32,768 position slots — which match the published configuration in Table 1, so the figures quoted in this report describe the checkpoint that actually ran.

**Embeddings and positions.** Each token id selects a row of the embedding matrix *E* (vocabulary × *d*): 1,536 numbers per token for Qwen, 768 for GPT-2. GPT-2 adds a learned vector for each absolute position; Qwen rotates every query and key vector by an angle proportional to its position (RoPE [6]), so attention depends on the *relative* distance between tokens.

**Masked self-attention.** Each decoder block normalises its input, applies masked multi-head self-attention, adds the result back (a residual connection), then applies a feed-forward network, again with a residual [2]. For one head:

<p class="eq"><img src="../assets/eq_attention.svg" alt="Attention(Q,K,V) = softmax(QK^T / sqrt(d_k) + M) V"></p>

Dividing by √*d*<sub>k</sub> keeps the softmax from saturating. *M* makes the model causal: it is 0 on and below the diagonal and −∞ above it, so each position attends only to earlier ones, which is why generation can run left to right. Qwen's 12 query heads share 2 key/value heads (GQA [7]). During generation the keys and values of earlier tokens are cached, and GQA shrinks that cache six-fold, to 28,672 bytes per token in fp16 instead of 172,032 — smaller than GPT-2's 36,864 even though Qwen is twelve times larger. The feed-forward layers hold most of the weights: 41.3 M of each Qwen block's 46.8 M parameters.

**Language-modelling head.** The final hidden state at the last position, *h*<sub>t</sub>, is mapped to one score per vocabulary entry and normalised into probabilities:

<p class="eq"><img src="../assets/eq_lmhead.svg" alt="z = W h_t, p(x_t+1 = i | x_<=t) = softmax(z)_i"></p>

Both models tie *W* to the embedding matrix, so the matrix that reads tokens in also writes them out.

**Autoregressive generation.** The prompt is processed once (the *prefill*); one token is chosen from *p*, appended and fed back, and the loop repeats until an end-of-sequence token or 192 new tokens. *How* the token is chosen is the decoding rule (§8), and it sits outside the model. Qwen's published generation configuration ships `do_sample=True, temperature=0.7, top_k=20, top_p=0.8, repetition_penalty=1.1`; left in place, every "temperature only" run would also apply top-k, top-p and a repetition penalty. Our generator resets all of them before applying a decoding configuration.

**What this explains about our design.** (1) The model writes JSON one token at a time with no notion of validity, so structure is enforced after generation by extraction, schema validation and repair (§10). (2) An intent label is just a token sequence, so the model can produce a plausible label that does not exist; every label is checked against the 77 real names. (3) The `confidence` the model writes is generated digits, not its softmax probability, so we use it only as an escalation signal and do not treat it as calibrated (§13). (4) Prefill cost grows with prompt length, and the label catalogue dominates the prompt: the strongest practical argument for fine-tuning (§9). (5) Under any sampling rule the same query can receive a different label on a different seed, which is why §8 measures self-consistency.
