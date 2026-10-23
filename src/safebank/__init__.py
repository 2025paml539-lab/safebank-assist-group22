"""
SafeBank Assist - a first-line banking support triage assistant.

PCAM ZG516 Applied Generative AI, Group Major Project / Assignment-1, Group 22.

The application takes one free-text customer message and returns a validated,
machine-readable decision: the predicted BANKING77 intent, a confidence value,
a customer-safe reply, an optional simulated tool call, and an escalation flag.

Package layout
--------------
``config``      Every tunable constant. Seeds, model ids, thresholds, paths.
``intents``     Label-space helpers, the E6 focus subset and confusable pairs.
``schema``      The structured-output contract, parsing and repair (E4).
``tools``       Three simulated tools, their I/O schemas and the router (E5).
``generator``   The ``TextGenerator`` seam, ``DecodeConfig``, ``FakeGenerator``.
``prompts``     Four parameterized prompt strategies (E2).
``pipeline``    End-to-end orchestration (E7).
``decoding``    Decoding grid for E3.            [interface only]
``data_prep``   BANKING77 load and sampling.     [interface only]
``model_loader``HF model/tokenizer loading.      [interface only]
``evaluate``    The six evaluation metrics.      [interface only]

Why this import is deliberately lightweight
-------------------------------------------
Nothing re-exported here imports ``torch``, ``transformers`` or ``datasets``.
The application depends on the ``TextGenerator`` protocol, not on a model
runtime, so ``import safebank`` works - and the whole test suite runs - with
only pydantic installed. The modules that *do* need a model runtime
(``model_loader``, ``data_prep``) are intentionally not imported here; import
them directly where a runtime is available, such as the Colab notebook.

Owner: Kishore (solution architecture)
"""

from __future__ import annotations

from . import config, intents, prompts, schema, tools
from .generator import (
    DecodeConfig,
    DecodeStrategy,
    FakeGenerator,
    TextGenerator,
)
from .intents import (
    CONFUSABLE_PAIRS,
    FOCUS_INTENTS,
    INTENT_THEMES,
    ConfusablePair,
    LabelSpaceError,
    LabelSpaceReport,
    theme_of,
    validate_label_space,
)
from .pipeline import Attempt, PipelineResult, SafeBankPipeline
from .prompts import (
    STRATEGY_RATIONALE,
    PromptStrategy,
    build_prompt,
    implemented_strategies,
    pending_strategies,
)
from .schema import (
    AssistantResponse,
    FailureKind,
    ToolCall,
    ToolName,
    ValidationOutcome,
    build_repair_prompt,
    extract_json_block,
    parse_response,
    response_json_schema,
)
from .tools import (
    INTENT_TO_TOOL,
    TOOL_REGISTRY,
    ToolExecutionError,
    ToolResult,
    ToolSpec,
    execute_tool,
    route_intent,
    tool_specs_json,
)

__version__ = "0.1.0"

#: Human-readable application name, used in the report and the demo.
APP_NAME = "SafeBank Assist"

__all__ = [
    # submodules
    "config",
    "intents",
    "prompts",
    "schema",
    "tools",
    # metadata
    "APP_NAME",
    "__version__",
    # structured output (E4)
    "AssistantResponse",
    "FailureKind",
    "ToolCall",
    "ToolName",
    "ValidationOutcome",
    "build_repair_prompt",
    "extract_json_block",
    "parse_response",
    "response_json_schema",
    # tools (E5)
    "INTENT_TO_TOOL",
    "TOOL_REGISTRY",
    "ToolExecutionError",
    "ToolResult",
    "ToolSpec",
    "execute_tool",
    "route_intent",
    "tool_specs_json",
    # generation seam
    "DecodeConfig",
    "DecodeStrategy",
    "FakeGenerator",
    "TextGenerator",
    # prompts (E2)
    "STRATEGY_RATIONALE",
    "PromptStrategy",
    "build_prompt",
    "implemented_strategies",
    "pending_strategies",
    # label space (E6)
    "CONFUSABLE_PAIRS",
    "FOCUS_INTENTS",
    "INTENT_THEMES",
    "ConfusablePair",
    "LabelSpaceError",
    "LabelSpaceReport",
    "theme_of",
    "validate_label_space",
    # pipeline (E7)
    "Attempt",
    "PipelineResult",
    "SafeBankPipeline",
]
