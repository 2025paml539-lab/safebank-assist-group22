"""
Offline test suite for SafeBank Assist.

Scope
-----
These tests cover the solution-architecture and application layer only, which
is Kishore's deliverable: the structured-output contract (E4), the simulated
tool layer (E5), the end-to-end pipeline (E7), the generation seam, the label
space, and the zero-shot reference prompt.

Deliberately NOT covered here, because they belong to other members and do not
exist yet: ``decoding.py`` and ``evaluate.py`` (Satya), ``data_prep.py`` and
``model_loader.py`` (Vishruth).

Framework
---------
Standard-library ``unittest``, not pytest, so every test here runs on a stock
interpreter plus pydantic with no extra dependency.

Zero model dependency
---------------------
No model runtime is required: torch, transformers, datasets and tokenizers are
not needed. The suite still exercises the full application control flow,
because ``pipeline.SafeBankPipeline`` depends on the ``TextGenerator``
protocol rather than on a model runtime, and ``FakeGenerator`` satisfies that
protocol with scripted completions. This is the practical payoff of the seam
described in ``ARCHITECTURE.md``.

Running
-------
From the project root (``GenAI_Project1``)::

    python -m unittest discover -s tests -t . -v

The ``sys.path`` insert below puts ``src`` on the import path so the suite
needs no installation step and no PYTHONPATH juggling.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
