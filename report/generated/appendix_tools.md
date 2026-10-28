```json
{
  "check_card_delivery_status": {
    "description": "Return the courier status and ETA for a card in transit.",
    "destructive": false,
    "input_schema": {
      "additionalProperties": false,
      "properties": {
        "card_id": {
          "description": "Synthetic card reference.",
          "minLength": 3,
          "title": "Card Id",
          "type": "string"
        }
      },
      "required": [
        "card_id"
      ],
      "title": "CardDeliveryInput",
      "type": "object"
    },
    "output_schema": {
      "properties": {
        "status": {
          "title": "Status",
          "type": "string"
        },
        "dispatched_on": {
          "title": "Dispatched On",
          "type": "string"
        },
        "eta_days": {
          "title": "Eta Days",
          "type": "integer"
        }
      },
      "required": [
        "status",
        "dispatched_on",
        "eta_days"
      ],
      "title": "CardDeliveryOutput",
      "type": "object"
    },
    "triggered_by": [
      "card_arrival",
      "card_delivery_estimate",
      "getting_spare_card",
      "order_physical_card"
    ]
  },
  "block_card": {
    "description": "Block a card and raise a replacement. Changes account state.",
    "destructive": true,
    "input_schema": {
      "$defs": {
        "BlockReason": {
          "enum": [
            "lost",
            "stolen",
            "compromised",
            "damaged"
          ],
          "title": "BlockReason",
          "type": "string"
        }
      },
      "additionalProperties": false,
      "properties": {
        "account_id": {
          "description": "Synthetic account reference.",
          "minLength": 3,
          "title": "Account Id",
          "type": "string"
        },
        "reason": {
          "$ref": "#/$defs/BlockReason",
          "description": "Why the card is being blocked."
        }
      },
      "required": [
        "account_id",
        "reason"
      ],
      "title": "BlockCardInput",
      "type": "object"
    },
    "output_schema": {
      "properties": {
        "blocked": {
          "title": "Blocked",
          "type": "boolean"
        },
        "ref_id": {
          "title": "Ref Id",
          "type": "string"
        },
        "replacement_eta_days": {
          "title": "Replacement Eta Days",
          "type": "integer"
        }
      },
      "required": [
        "blocked",
        "ref_id",
        "replacement_eta_days"
      ],
      "title": "BlockCardOutput",
      "type": "object"
    },
    "triggered_by": [
      "card_swallowed",
      "compromised_card",
      "lost_or_stolen_card"
    ]
  },
  "find_branch": {
    "description": "Find the nearest branch or ATM offering a given service.",
    "destructive": false,
    "input_schema": {
      "$defs": {
        "BranchService": {
          "enum": [
            "cash_deposit",
            "atm",
            "card_collection",
            "identity_verification"
          ],
          "title": "BranchService",
          "type": "string"
        }
      },
      "additionalProperties": false,
      "properties": {
        "pincode": {
          "description": "Area pincode.",
          "maxLength": 10,
          "minLength": 4,
          "title": "Pincode",
          "type": "string"
        },
        "service": {
          "$ref": "#/$defs/BranchService",
          "description": "Service the customer needs."
        }
      },
      "required": [
        "pincode",
        "service"
      ],
      "title": "FindBranchInput",
      "type": "object"
    },
    "output_schema": {
      "properties": {
        "branch_name": {
          "title": "Branch Name",
          "type": "string"
        },
        "address": {
          "title": "Address",
          "type": "string"
        },
        "distance_km": {
          "title": "Distance Km",
          "type": "number"
        }
      },
      "required": [
        "branch_name",
        "address",
        "distance_km"
      ],
      "title": "FindBranchOutput",
      "type": "object"
    },
    "triggered_by": [
      "atm_support",
      "cash_withdrawal_charge",
      "declined_cash_withdrawal"
    ]
  }
}
```

Direct invocations of the simulated tools with synthetic arguments. The last call shows argument validation rejecting a malformed pincode. `block_card` works when called directly, but the pipeline never calls it automatically; it escalates for customer confirmation instead (§10).

```json
[
  {
    "tool": "check_card_delivery_status",
    "args": {
      "card_id": "CARD_SIM_0001"
    },
    "result": {
      "ok": true,
      "tool": "check_card_delivery_status",
      "output": {
        "status": "in_transit",
        "dispatched_on": "2026-10-12",
        "eta_days": 5
      },
      "error": null
    }
  },
  {
    "tool": "find_branch",
    "args": {
      "pincode": "560001",
      "service": "atm"
    },
    "result": {
      "ok": true,
      "tool": "find_branch",
      "output": {
        "branch_name": "Market Street Branch",
        "address": "114 High Road, 560001",
        "distance_km": 2.1
      },
      "error": null
    }
  },
  {
    "tool": "block_card",
    "args": {
      "account_id": "ACC_SIM_0001",
      "reason": "lost"
    },
    "result": {
      "ok": true,
      "tool": "block_card",
      "output": {
        "blocked": true,
        "ref_id": "BLK-223132",
        "replacement_eta_days": 7
      },
      "error": null
    }
  },
  {
    "tool": "find_branch",
    "args": {
      "pincode": "56",
      "service": "atm"
    },
    "result": {
      "ok": false,
      "tool": "find_branch",
      "output": null,
      "error": "invalid args: pincode: String should have at least 4 characters"
    }
  }
]
```
