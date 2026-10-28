```json
{
  "$defs": {
    "ToolCall": {
      "additionalProperties": false,
      "description": "A request from the model to invoke one tool.",
      "properties": {
        "name": {
          "$ref": "#/$defs/ToolName",
          "description": "Which tool to invoke."
        },
        "args": {
          "additionalProperties": {
            "type": "string"
          },
          "description": "Flat string arguments; validated again by the tool itself.",
          "title": "Args",
          "type": "object"
        }
      },
      "required": [
        "name"
      ],
      "title": "ToolCall",
      "type": "object"
    },
    "ToolName": {
      "description": "The tools the assistant is permitted to request.\n\nUsing an enum rather than a free string means a hallucinated tool name is\ncaught by schema validation instead of reaching the router.",
      "enum": [
        "check_card_delivery_status",
        "block_card",
        "find_branch"
      ],
      "title": "ToolName",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "description": "The machine-readable contract for one assistant turn.\n\n``extra=\"forbid\"`` is intentional: if the model invents a field, we want a\nvalidation failure we can count in E4, not a silently ignored key.",
  "properties": {
    "intent": {
      "description": "Predicted BANKING77 intent name, exactly as in the dataset.",
      "title": "Intent",
      "type": "string"
    },
    "confidence": {
      "description": "Model's self-reported confidence in the intent.",
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Confidence",
      "type": "number"
    },
    "response": {
      "description": "Customer-facing reply, safe to show as-is.",
      "minLength": 1,
      "title": "Response",
      "type": "string"
    },
    "tool_call": {
      "anyOf": [
        {
          "$ref": "#/$defs/ToolCall"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Tool to invoke, or null if none is needed."
    },
    "requires_human": {
      "default": false,
      "description": "True when the request must be escalated.",
      "title": "Requires Human",
      "type": "boolean"
    },
    "disclaimer": {
      "default": "Information shown is from a simulated system of record, not live banking data.",
      "description": "Mandatory provenance notice attached to every response.",
      "title": "Disclaimer",
      "type": "string"
    }
  },
  "required": [
    "intent",
    "confidence",
    "response"
  ],
  "title": "AssistantResponse",
  "type": "object"
}
```
