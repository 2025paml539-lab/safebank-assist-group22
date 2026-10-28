# 2. Problem statement and motivation

**Target user.** A tier-1 customer-support agent at a retail bank, and through a self-service chat channel, the customer.

**Problem.** Messages arrive as free text. For each one the agent must decide what the customer wants among 77 fine-grained request types (BANKING77 [1]), whether a system lookup or action is needed, and how to reply safely. Done by hand this is slow and inconsistent between agents, and the hard cases are the near-identical ones: "my card hasn't arrived" (a status question) versus "when will my card arrive" (a timing question).

**Input and output.** The input is one customer message. The output is one validated JSON object:

```json
{"intent": "card_arrival", "confidence": 0.82,
 "response": "I can see your card was dispatched. Let me check the delivery status.",
 "tool_call": {"name": "check_card_delivery_status", "args": {"card_id": "CARD_0417"}},
 "requires_human": false,
 "disclaimer": "Information shown is from a simulated system of record, not live banking data."}
```

**Application scenario.** The assistant drafts the triage decision. Deterministic code, not the model, decides whether a tool runs, whether the reply is shown, and whether a person takes over.

**Why a generative LLM.** A 77-way classifier returns a label and nothing else. This task needs four outputs at once: the label, a reply the customer can read, a decision about calling a system, and a structured record that a downstream system can act on. A prompted causal language model produces all four in a single pass, and absorbs a new intent through a prompt edit rather than retraining. The price is that its output is unconstrained text: it can be malformed, name an intent that does not exist, or say something unsafe. Most of the engineering in this project (§5, §10, §12) exists to contain that risk.

**Scope.** All 77 intents stay in the label space for every metric. A 20-intent subset in five service themes is used only to organise the failure analysis (§3). We use pretrained checkpoints and train nothing.
