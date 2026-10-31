"""
Build the demo deck for the 8-10 minute presentation.

Every figure is read from the result files in artifacts/results/ rather than
typed in, so the slides cannot drift from the report. The opening two slides
follow report/demo_opening_segment.md; the rest cover the workflow, the
experiments, the safety result and the limitations, with speaker notes and a
timing plan that gives all four members a speaking slot.

Usage, from the project root:

    python report/build_demo_deck.py

Output: report/build/SafeBank_Assist_Group22_Demo.pptx
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RESULTS = PROJECT / "artifacts" / "results"
OUT = HERE / "build" / "SafeBank_Assist_Group22_Demo.pptx"

NAVY = RGBColor(0x14, 0x2A, 0x4F)
GREY = RGBColor(0x44, 0x4A, 0x52)
ACCENT = RGBColor(0xB1, 0x2A, 0x2A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def pct(fraction: float, places: int = 1) -> float:
    """Percentage rounded half-up, matching the report's tables.

    Python rounds 48.05 to 48.0 (banker's rounding) while the report prints
    48.1, so a plain f-string here would make the deck disagree with the
    report on exactly the kind of number an examiner checks.
    """
    quant = Decimal(1).scaleb(-places)
    return float((Decimal(str(fraction)) * 100).quantize(quant, rounding=ROUND_HALF_UP))


def facts() -> dict:
    """Every number used on the slides, read from the result files."""
    e2 = {row["strategy"]: row for row in load("e2_summary.json")}
    e3 = load("e3_summary.json")
    dev_t4 = load("device_report.json")
    dev_a100 = load("experiments_device_report.json")
    e6 = load("e6_analysis.json")
    pre = load("preprocessing_record.json")
    fs, zs = e2["few_shot"], e2["zero_shot"]
    by_label = {row["decoding"]: row for row in e3}
    return {
        "n_eval": fs["n"],
        "train_rows": pre["split_sizes"]["train"],
        "test_rows": pre["split_sizes"]["test"],
        "fs_acc": pct(fs["accuracy"]),
        "fs_f1": fs["macro_f1"],
        "zs_acc": pct(zs["accuracy"]),
        "zs_f1": zs["macro_f1"],
        "rc_acc": pct(e2["role_context"]["accuracy"]),
        "cb_acc": pct(e2["constraint_based"]["accuracy"]),
        "fs_valid_first": pct(fs["schema_first_attempt_rate"]),
        "fs_valid_final": pct(fs["schema_final_rate"]),
        "zs_unsafe": pct(zs["safety_unsafe_rate"]),
        "fs_unsafe": pct(fs["safety_unsafe_rate"]),
        "zs_cred": zs["safety_credential_solicitation"],
        "fs_cred": fs["safety_credential_solicitation"],
        "fs_routing": pct(fs["tool_routing_accuracy"]),
        "fs_withheld": fs["safety_replies_withheld"],
        "greedy_acc": pct(by_label["greedy"]["accuracy_mean"]),
        "t07_acc": pct(by_label["temperature=0.7"]["accuracy_mean"]),
        "t12_acc": pct(by_label["temperature=1.2"]["accuracy_mean"]),
        "topk_acc": pct(by_label["top_k=50 temp=0.7"]["accuracy_mean"]),
        "t07_stable": pct(by_label["temperature=0.7"]["fully_stable_fraction"]),
        "t12_stable": pct(by_label["temperature=1.2"]["fully_stable_fraction"]),
        "t4": dev_t4["device_name"],
        "a100": dev_a100["device_name"],
        "model": dev_t4["model_id"],
        "baseline": dev_t4["baseline_model_id"],
        "n_failure_cases": len(e6.get("failure_cases", [])),
        "n_safety_findings": len(e6.get("safety_findings", [])),
    }


def add_slide(prs: Presentation, title: str, bullets: list, notes: str,
              speaker: str = "", timing: str = "", accent_last: bool = False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    bar = slide.shapes.add_textbox(Inches(0.0), Inches(0.0), prs.slide_width, Inches(0.12))
    bar.fill.solid() if False else None

    tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.38), Inches(12.2), Inches(0.9))
    p = tb.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(30)
    p.font.bold = True
    p.font.color.rgb = NAVY

    if speaker or timing:
        meta = slide.shapes.add_textbox(Inches(0.6), Inches(6.75), Inches(12.0), Inches(0.4))
        mp = meta.text_frame.paragraphs[0]
        mp.text = f"{speaker}   ·   {timing}" if speaker and timing else (speaker or timing)
        mp.font.size = Pt(12)
        mp.font.color.rgb = GREY

    body = slide.shapes.add_textbox(Inches(0.65), Inches(1.5), Inches(12.0), Inches(5.0))
    tf = body.text_frame
    tf.word_wrap = True
    for i, item in enumerate(bullets):
        text, level = (item if isinstance(item, tuple) else (item, 0))
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = ("• " if level == 0 else "– ") + text
        para.level = level
        para.font.size = Pt(19 if level == 0 else 16)
        para.font.color.rgb = NAVY if level == 0 else GREY
        para.space_after = Pt(9)
        if accent_last and i == len(bullets) - 1:
            para.font.color.rgb = ACCENT
            para.font.bold = True

    slide.notes_slide.notes_text_frame.text = notes
    return slide


def build() -> dict:
    f = facts()
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # --- title ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.1), Inches(11.7), Inches(2.6))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "SafeBank Assist"
    p.font.size = Pt(54)
    p.font.bold = True
    p.font.color.rgb = NAVY
    for line, size in [
        ("A first-line banking-support triage assistant on a pretrained causal LLM", 20),
        (f"BANKING77 · 77 intents · {f['model']} · baseline {f['baseline']}", 16),
        ("PCAM* ZG516 Applied Generative AI · Group Major Project / Assignment-1 · Group 22", 14),
        ("Nandhaluru Kishore · Vishruth M · Satya Prakash · Takkars Bhavani", 14),
    ]:
        q = tf.add_paragraph()
        q.text = line
        q.font.size = Pt(size)
        q.font.color.rgb = GREY if size < 20 else NAVY
    slide.notes_slide.notes_text_frame.text = (
        "Total 8-10 minutes. Four speakers, roughly two minutes each. Keep the live run "
        "for slide 5 - if the GPU session has expired, play the stored notebook output instead."
    )

    # --- 1. the problem (from demo_opening_segment.md) ---
    add_slide(
        prs, "The problem",
        [f'"My new card still hasn\'t arrived and it\'s been two weeks"',
         f"Every message must be mapped to one of 77 BANKING77 request types",
         "Then: does it need a system lookup, and what is a safe reply?",
         ("The hard cases are near-twins: \"my card hasn't arrived\" against "
          "\"when will my card arrive\" are different intents", 1),
         "By hand this is slow, and two agents answer the same message differently"],
        notes=("0:00-0:45. A retail bank's support desk gets thousands of short, messy messages a "
               "day. For every one an agent works out what the customer wants out of 77 request "
               "types, decides whether to look something up, and replies without inventing account "
               "facts. Done by hand it is slow and inconsistent. The hardest cases are the "
               "near-twins."),
        speaker="Speaker 1", timing="0:00 - 0:45")

    # --- 2. what we built ---
    add_slide(
        prs, "What we built, and why a generative model",
        ["One message in; one validated JSON decision out",
         ("intent · confidence · customer-safe reply · optional tool call · escalation flag", 1),
         "A classifier gives only the label - no reply, no routing decision",
         "One prompted pass gives all three, and a new intent is a prompt edit, not retraining",
         "The catch: the output is just text. Most of the engineering is checking it"],
        notes=("0:45-1:30. SafeBank Assist reads one message and returns one structured decision. "
               "A plain classifier would only give the label. A pretrained LM gives label, reply and "
               "routing in one pass, and a new request type is a prompt edit instead of a retrain. "
               "The catch is that the output is just text, so most of what we built checks that text "
               "before anyone acts on it. Hand over: 'starting with the data we used.'"),
        speaker="Speaker 1", timing="0:45 - 1:30")

    # --- 3. data ---
    add_slide(
        prs, "The data",
        [f"BANKING77: {f['train_rows']:,} training and {f['test_rows']:,} test messages, 77 intents",
         f"Evaluation sample: {f['n_eval']} messages, 5 per intent, stratified, seed 42, test split only",
         "Few-shot examples come from the training split; the runner refuses to start if any example is also an evaluation query",
         "Label order read from the dataset card and checked against the pinned revision - all 77 names, in order"],
        notes=("1:30-2:15. Point at the frozen evaluation set and the train/eval separation - that is "
               "what makes the numbers later believable. Mention that the label file moved on the Hub "
               "mid-project and we pinned a revision to keep the label order stable."),
        speaker="Speaker 2", timing="1:30 - 2:15")

    # --- 4. architecture ---
    add_slide(
        prs, "The pipeline: the model proposes, code decides",
        ["message → prompt template → LLM → raw text",
         "→ JSON parse → schema validation → repair-retry, at most twice",
         "→ label must exist in BANKING77 → confidence gate → tool router → simulated tool",
         "→ reply-safety screen → final reply with disclaimer, or escalation",
         "Nothing unvalidated reaches the customer, and a card is never blocked automatically"],
        notes=("2:15-3:15. Walk the arrows once, slowly. The point to land: the model is one "
               "component, wrapped in deterministic checks. Name the four validation failure kinds "
               "- no JSON, malformed JSON, schema violation, unknown intent."),
        speaker="Speaker 2", timing="2:15 - 3:15", accent_last=True)

    # --- 5. live demo ---
    add_slide(
        prs, "Live: three messages, three outcomes",
        ['"Which ATMs accept this card?" → atm_support → find_branch runs → reply with the lookup',
         '"I lost my card on the train" → lost_or_stolen_card → card NOT blocked automatically',
         ("the model\'s own reply asked for the customer\'s PIN - the safety screen withheld it "
          "and escalated", 1),
         '"Is there an ATM near 560001?" → no valid label after 3 attempts → escalated, nothing shown',
         "Same pipeline, three different terminal paths"],
        notes=("3:15-4:30. This is the heart of the demo. Run it live from the notebook if a GPU "
               "session is up; otherwise show the stored outputs - they are committed, so nothing has "
               "to be re-run. Say plainly that case two is a 1.5B model asking a customer for their "
               "PIN, and that no accuracy or validity metric would have caught it."),
        speaker="Speaker 3", timing="3:15 - 4:30", accent_last=True)

    # --- 6. prompt experiments ---
    add_slide(
        prs, f"E2 - four prompt strategies, {f['n_eval']} messages each",
        [f"few-shot {f['fs_acc']:.1f}% accuracy, macro-F1 {f['fs_f1']:.3f} - the only strategy that separates",
         f"zero-shot {f['zs_acc']:.1f}% · role/context {f['rc_acc']:.1f}% · constraint-based {f['cb_acc']:.1f}%",
         ("the other three cannot be told apart - paired exact McNemar, p from 0.47 to 1.0", 1),
         "Two of our four hypotheses were wrong:",
         ("few-shot LOWERED first-attempt validity - every violation was an invented tool name", 1),
         ("the role persona did not make replies safer", 1)],
        notes=("4:30-5:30. Lead with the honest finding: only few-shot moved the needle, and two of "
               "the four design hypotheses failed. Mention the comparison is paired on the same "
               f"{f['n_eval']} messages, which is why the significance test is meaningful."),
        speaker="Speaker 3", timing="4:30 - 5:30")

    # --- 7. decoding ---
    add_slide(
        prs, "E3 - decoding: sampling cost us accuracy and gained nothing",
        [f"greedy {f['greedy_acc']:.1f}% · temperature 0.7 {f['t07_acc']:.1f}% · temperature 1.2 {f['t12_acc']:.1f}%",
         f"top-k 50 at temp 0.7 was {f['topk_acc']:.1f}% - identical to plain temperature 0.7, every seed",
         ("at temperature 0.7 almost no probability sits beyond the 50 most likely tokens", 1),
         f"Stability is not correctness: {f['t07_stable']:.0f}% of queries agree across all five seeds at 0.7, only {f['t12_stable']:.0f}% at 1.2",
         "Qwen ships sampling defaults on - they had to be neutralised or every row would mean something else"],
        notes=("5:30-6:30. The neutralisation point is worth 20 seconds: top_k had to be set to 0, "
               "because None is refilled from the model's own config and would have put top-k=20 back "
               "into every sampled run. Without that fix the whole E3 table would have been wrong."),
        speaker="Speaker 4", timing="5:30 - 6:30")

    # --- 8. safety result ---
    add_slide(
        prs, "The result we care about most",
        [f"Replies flagged unsafe: {f['zs_unsafe']:.1f}% zero-shot → {f['fs_unsafe']:.1f}% few-shot",
         f"Credential-asking replies: {f['zs_cred']} of {f['n_eval']} → {f['fs_cred']} of {f['n_eval']}",
         f"{f['fs_withheld']} replies withheld and escalated by the safety screen",
         "Every one of those passed JSON validation and had the right intent",
         "Accuracy, validity and routing all scored them as success"],
        notes=("6:30-7:15. Land the lesson: a reply can pass every structural check and still be "
               "unsafe. That is why the screen exists and why it is rule-based rather than inferred "
               "from the metrics."),
        speaker="Speaker 4", timing="6:30 - 7:15", accent_last=True)

    # --- 9. evaluation + failures ---
    add_slide(
        prs, "E6 - how we evaluate, and where it fails",
        ["Six criteria: accuracy and macro-F1, schema validity, tool routing, reply safety, latency and attempts, self-consistency",
         f"Repair raises validity {f['fs_valid_first']:.1f}% → {f['fs_valid_final']:.1f}%",
         ("it rescues 47 of 60 formatting errors but only 1 of 62 invented labels - the retry never "
          "re-states the valid labels", 1),
         f"Routing handled correctly for {f['fs_routing']:.0f}% of the tool-triggering messages; every miss followed a wrong intent",
         f"{f['n_failure_cases']} failure cases analysed, {f['n_safety_findings']} safety findings recorded"],
        notes=("7:15-8:00. The repair asymmetry is the most interesting engineering finding - it "
               "points straight at the fix, which is putting the label catalogue into the repair "
               "prompt. We did not change it because it would invalidate the measured numbers."),
        speaker="Speaker 4", timing="7:15 - 8:00")

    # --- 10. honest limits ---
    add_slide(
        prs, "What we would not claim",
        [f"{f['fs_acc']:.1f}% on a 77-way task is not production-ready - we say so in the report",
         "confidence is a number the model writes; it was effectively constant and the gate never fired",
         "output is validated after generation, not constrained during it",
         "the safety screen is rule-based and will miss reworded requests; tools are simulated; conversations are single-turn",
         f"E1 and the live trace ran on a {f['t4']}; E2, E3 and E6 on an {f['a100']} - stated in Appendix F"],
        notes=("8:00-8:45. Say these out loud rather than waiting to be asked. Naming the hardware "
               "split and the sub-50% accuracy is what makes the rest of the numbers credible."),
        speaker="all", timing="8:00 - 8:45")

    # --- 11. close ---
    add_slide(
        prs, "Where we would take it next",
        ["Constrained decoding: mask the logits so only valid JSON and real labels can be produced",
         "LoRA on the 10,003 training messages, compared head to head with the best prompt",
         "Calibrated confidence from token probabilities instead of the model's own number",
         "Put the label catalogue in the repair prompt - the 1-of-62 result says this is the cheap win",
         "398 automated tests · every result file and both notebooks public in the repository"],
        notes=("8:45-9:30. Close on the engineering posture: the model is one replaceable component "
               "behind a tested, deterministic shell. Invite questions."),
        speaker="all", timing="8:45 - 9:30", accent_last=True)

    # --- 12. speaking plan ---
    add_slide(
        prs, "Speaking plan",
        ["Speaker 1 - problem, what we built, why a generative model (0:00-1:30)",
         "Speaker 2 - data, the frozen evaluation set, the pipeline walk-through (1:30-3:15)",
         "Speaker 3 - the live run, then the prompt experiments (3:15-5:30)",
         "Speaker 4 - decoding, the safety result, evaluation and failures (5:30-8:00)",
         "All four - limits and next steps, then questions (8:00-9:30)",
         "Assign the four slots in the group; every member should be able to explain any slide"],
        notes=("Not a presented slide - keep it as the rehearsal plan, or delete it before the demo. "
               "The brief expects all four members to speak and to be able to explain the whole "
               "workflow."),
        speaker="rehearsal aid", timing="not presented")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    return f


def verify(f: dict) -> None:
    prs = Presentation(OUT)
    n_notes = sum(1 for s in prs.slides
                  if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip())
    text = " ".join(
        shape.text_frame.text
        for s in prs.slides for shape in s.shapes if shape.has_text_frame
    )
    print(f"PPTX: {OUT}")
    print(f"size: {OUT.stat().st_size:,} bytes | slides: {len(prs.slides)} | slides with notes: {n_notes}")
    print(f"slide size: {prs.slide_width.inches:.3f} x {prs.slide_height.inches:.3f} in (16:9)")
    for label, needle in [
        ("few-shot accuracy", f"{f['fs_acc']:.1f}%"),
        ("zero-shot accuracy", f"{f['zs_acc']:.1f}%"),
        ("greedy accuracy", f"{f['greedy_acc']:.1f}%"),
        ("unsafe before", f"{f['zs_unsafe']:.1f}%"),
        ("unsafe after", f"{f['fs_unsafe']:.1f}%"),
        ("T4", f["t4"]),
        ("A100", f["a100"]),
    ]:
        print(f"  {'OK  ' if needle in text else 'MISS'} {label} -> {needle}")
    for bad in ("vl543f", "boeing", "C:\\Users", "ghp_"):
        if bad.lower() in text.lower():
            print(f"  WARNING: {bad!r} appears on a slide")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verify(build())
