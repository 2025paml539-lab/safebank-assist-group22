"""
Central configuration for SafeBank Assist.

Every tunable constant lives here so experiments stay reproducible and the
report can quote exact settings. Nothing here imports a heavy framework, so it
is safe to import from anywhere, including offline tests.

Owner: Kishore (solution architecture)
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------

#: Single global seed, quoted in the report's reproducibility appendix.
SEED: int = 42

# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

#: Primary instruction-tuned causal LM used for the final system.
MODEL_ID: str = "Qwen/Qwen2.5-1.5B-Instruct"

#: Deliberately weak baseline (E1), to make the improvement curve visible.
BASELINE_MODEL_ID: str = "gpt2"

# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------

DATASET_ID: str = "PolyAI/banking77"

#: BANKING77 has exactly 77 intents and we keep the full label space.
#: Fine-grained 77-way intent classification is the defining characteristic of
#: this dataset; narrowing it would weaken the dataset analysis. Authoritative
#: names come from the dataset itself at load time, never hardcoded.
EXPECTED_N_INTENTS: int = 77

#: Stratified evaluation sample: examples per intent.
#: 5 x 77 = 385 rows. Fast on a 1.5B model, every intent represented.
EVAL_EXAMPLES_PER_INTENT: int = 5

# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

MAX_NEW_TOKENS: int = 192

#: Below this confidence the pipeline escalates instead of acting.
ESCALATION_CONFIDENCE_THRESHOLD: float = 0.55

#: How many times the pipeline may ask the model to repair malformed JSON
#: before escalating. Measured in E4 as validity-rate lift.
REPAIR_MAX_ATTEMPTS: int = 2

# --------------------------------------------------------------------------
# Safety
# --------------------------------------------------------------------------

#: Appended to every customer-facing response. Responsible-use control: the
#: user must never mistake simulated data for a real system of record.
SAFETY_DISCLAIMER: str = (
    "Information shown is from a simulated system of record, not live banking data."
)

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts"
DATA_DIR: Path = ARTIFACTS_DIR / "data"
RESULTS_DIR: Path = ARTIFACTS_DIR / "results"
FIGURES_DIR: Path = ARTIFACTS_DIR / "figures"


def ensure_dirs() -> None:
    """Create artifact directories if they do not already exist."""
    for path in (ARTIFACTS_DIR, DATA_DIR, RESULTS_DIR, FIGURES_DIR):
        path.mkdir(parents=True, exist_ok=True)
