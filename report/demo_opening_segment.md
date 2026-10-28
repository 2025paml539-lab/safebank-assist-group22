# Demo — opening segment (0:00–1:30)

Covers the first block of the 8–10 minute demo: the problem, the user and why an LLM. About 220 words, roughly 90 seconds at a normal speaking pace. The next speaker picks up with the dataset and the baseline.

## Slide 1 — The problem (0:00–0:45)

**On screen:** title "SafeBank Assist"; one sample message, *"My new card still hasn't arrived and it's been two weeks"*; the number **77**.

**Say:**

> A retail bank's support desk gets thousands of short, messy messages a day. For every one, an agent has to work out what the customer actually wants — out of 77 possible request types in the BANKING77 dataset — decide whether to look something up, and reply without making up facts about the customer's account. Done by hand that's slow, and different agents answer the same message differently. The hardest cases are the near-twins: "my card hasn't arrived" and "when will my card arrive" are different requests.

## Slide 2 — What we built and why an LLM (0:45–1:30)

**On screen:** the JSON output from §2 of the report; three icons — label, reply, tool.

**Say:**

> SafeBank Assist reads one message and returns one structured decision: the intent, a reply the customer can read, an optional call to a banking tool, and a flag to hand over to a human. A plain classifier would only give us the label. A pretrained language model gives us the label, the reply and the routing decision in one pass, and we can add a new request type by editing the prompt instead of retraining. The catch is that its output is just text — so most of what we built is about checking that text before anyone acts on it. That's what the rest of this demo shows.

**Hand over:** "…starting with the data we used."
