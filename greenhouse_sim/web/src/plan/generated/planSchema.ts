// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/plan.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const PLAN_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "Action": {
      "oneOf": [
        {
          "$ref": "#/$defs/SetLevel"
        },
        {
          "$ref": "#/$defs/SetTarget"
        },
        {
          "$ref": "#/$defs/Water"
        },
        {
          "$ref": "#/$defs/Harvest"
        },
        {
          "$ref": "#/$defs/Lower"
        },
        {
          "$ref": "#/$defs/RemoveLeaf"
        },
        {
          "$ref": "#/$defs/Inspect"
        }
      ]
    },
    "ActionId": {
      "minLength": 1,
      "pattern": "^[A-Za-z0-9_.-]+$",
      "type": "string"
    },
    "Asap": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "asap",
          "default": "asap",
          "title": "Kind",
          "type": "string"
        },
        "deadline": {
          "anyOf": [
            {
              "$ref": "#/$defs/Instant"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "title": "Asap",
      "type": "object"
    },
    "At": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "at",
          "default": "at",
          "title": "Kind",
          "type": "string"
        },
        "at": {
          "$ref": "#/$defs/Instant"
        }
      },
      "required": [
        "at"
      ],
      "title": "At",
      "type": "object"
    },
    "ExecutorKind": {
      "enum": [
        "simulated_run",
        "person",
        "robot",
        "climate_computer"
      ],
      "title": "ExecutorKind",
      "type": "string"
    },
    "ExecutorRef": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "$ref": "#/$defs/ExecutorKind"
        },
        "id": {
          "anyOf": [
            {
              "$ref": "#/$defs/Name"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "kind"
      ],
      "title": "ExecutorRef",
      "type": "object"
    },
    "Harvest": {
      "additionalProperties": false,
      "else": {
        "properties": {
          "organ_id": {
            "type": "string"
          }
        },
        "required": [
          "organ_id"
        ]
      },
      "if": {
        "properties": {
          "scope": {
            "const": "ripe"
          }
        }
      },
      "properties": {
        "kind": {
          "const": "harvest",
          "default": "harvest",
          "title": "Kind",
          "type": "string"
        },
        "plant_id": {
          "$ref": "#/$defs/ItemName"
        },
        "scope": {
          "$ref": "#/$defs/HarvestScope"
        },
        "organ_id": {
          "anyOf": [
            {
              "$ref": "#/$defs/ItemName"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "plant_id",
        "scope"
      ],
      "then": {
        "properties": {
          "organ_id": {
            "type": "null"
          }
        }
      },
      "title": "Harvest",
      "type": "object"
    },
    "HarvestScope": {
      "enum": [
        "ripe",
        "fruit",
        "truss"
      ],
      "title": "HarvestScope",
      "type": "string"
    },
    "Identifier": {
      "minLength": 1,
      "pattern": "^[A-Za-z0-9_.-]+$",
      "type": "string"
    },
    "IfPrerequisiteFails": {
      "enum": [
        "cancel",
        "proceed"
      ],
      "title": "IfPrerequisiteFails",
      "type": "string"
    },
    "Inspect": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "inspect",
          "default": "inspect",
          "title": "Kind",
          "type": "string"
        },
        "plant_id": {
          "$ref": "#/$defs/ItemName"
        },
        "reason": {
          "minLength": 1,
          "title": "Reason",
          "type": "string"
        }
      },
      "required": [
        "plant_id",
        "reason"
      ],
      "title": "Inspect",
      "type": "object"
    },
    "Instant": {
      "format": "date-time",
      "type": "string"
    },
    "ItemName": {
      "minLength": 1,
      "type": "string"
    },
    "Lateness": {
      "additionalProperties": false,
      "else": {
        "properties": {
          "fallback": {
            "type": "null"
          }
        }
      },
      "if": {
        "properties": {
          "on_late": {
            "const": "fallback"
          }
        },
        "required": [
          "on_late"
        ]
      },
      "properties": {
        "tolerance_s": {
          "default": 0,
          "minimum": 0,
          "title": "Tolerance S",
          "type": "number"
        },
        "on_late": {
          "$ref": "#/$defs/OnLate",
          "default": "run_late"
        },
        "fallback": {
          "anyOf": [
            {
              "$ref": "#/$defs/Action"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "then": {
        "properties": {
          "fallback": {
            "not": {
              "type": "null"
            }
          }
        },
        "required": [
          "fallback"
        ]
      },
      "title": "Lateness",
      "type": "object"
    },
    "Lower": {
      "additionalProperties": false,
      "oneOf": [
        {
          "properties": {
            "by_cm": {
              "type": "number"
            }
          },
          "required": [
            "by_cm"
          ]
        },
        {
          "properties": {
            "by_internodes": {
              "type": "integer"
            }
          },
          "required": [
            "by_internodes"
          ]
        },
        {
          "properties": {
            "to_head_room_m": {
              "type": "number"
            }
          },
          "required": [
            "to_head_room_m"
          ]
        }
      ],
      "properties": {
        "kind": {
          "const": "lower",
          "default": "lower",
          "title": "Kind",
          "type": "string"
        },
        "plant_id": {
          "$ref": "#/$defs/ItemName"
        },
        "by_cm": {
          "anyOf": [
            {
              "exclusiveMinimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "By Cm"
        },
        "by_internodes": {
          "anyOf": [
            {
              "exclusiveMinimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "By Internodes"
        },
        "to_head_room_m": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "To Head Room M"
        }
      },
      "required": [
        "plant_id"
      ],
      "title": "Lower",
      "type": "object"
    },
    "Name": {
      "minLength": 1,
      "type": "string"
    },
    "OnLate": {
      "enum": [
        "run_late",
        "skip",
        "critical",
        "fallback",
        "abort_plan"
      ],
      "title": "OnLate",
      "type": "string"
    },
    "PlannedAction": {
      "additionalProperties": false,
      "properties": {
        "action_id": {
          "$ref": "#/$defs/ActionId"
        },
        "action": {
          "$ref": "#/$defs/Action"
        },
        "timing": {
          "$ref": "#/$defs/Timing"
        },
        "every": {
          "anyOf": [
            {
              "$ref": "#/$defs/Recurrence"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "after": {
          "default": [],
          "items": {
            "$ref": "#/$defs/ActionId"
          },
          "title": "After",
          "type": "array"
        },
        "if_prerequisite_fails": {
          "$ref": "#/$defs/IfPrerequisiteFails",
          "default": "cancel"
        },
        "lateness": {
          "$ref": "#/$defs/Lateness",
          "default": {
            "tolerance_s": 0,
            "on_late": "run_late",
            "fallback": null
          }
        },
        "expected_duration_s": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expected Duration S"
        },
        "executed_by": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/ExecutorRef"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Executed By"
        },
        "proposed_by": {
          "$ref": "#/$defs/Principal"
        }
      },
      "required": [
        "action_id",
        "action",
        "timing",
        "proposed_by"
      ],
      "title": "PlannedAction",
      "type": "object"
    },
    "Principal": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "$ref": "#/$defs/PrincipalKind"
        },
        "id": {
          "$ref": "#/$defs/Name"
        }
      },
      "required": [
        "kind",
        "id"
      ],
      "title": "Principal",
      "type": "object"
    },
    "PrincipalKind": {
      "enum": [
        "person",
        "policy",
        "schedule",
        "scenario",
        "platform"
      ],
      "title": "PrincipalKind",
      "type": "string"
    },
    "Recurrence": {
      "additionalProperties": false,
      "oneOf": [
        {
          "properties": {
            "count": {
              "type": "integer"
            }
          },
          "required": [
            "count"
          ]
        },
        {
          "properties": {
            "until": {
              "type": "string"
            }
          },
          "required": [
            "until"
          ]
        }
      ],
      "properties": {
        "period": {
          "format": "duration",
          "title": "Period",
          "type": "string"
        },
        "count": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Count"
        },
        "until": {
          "anyOf": [
            {
              "$ref": "#/$defs/Instant"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "period"
      ],
      "title": "Recurrence",
      "type": "object"
    },
    "RemoveLeaf": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "remove_leaf",
          "default": "remove_leaf",
          "title": "Kind",
          "type": "string"
        },
        "plant_id": {
          "$ref": "#/$defs/ItemName"
        },
        "leaf_id": {
          "$ref": "#/$defs/ItemName"
        }
      },
      "required": [
        "plant_id",
        "leaf_id"
      ],
      "title": "RemoveLeaf",
      "type": "object"
    },
    "SetLevel": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "set_level",
          "default": "set_level",
          "title": "Kind",
          "type": "string"
        },
        "device_id": {
          "$ref": "#/$defs/ItemName"
        },
        "level": {
          "anyOf": [
            {
              "maximum": 1,
              "minimum": 0,
              "type": "number"
            },
            {
              "const": "auto",
              "type": "string"
            }
          ],
          "title": "Level"
        }
      },
      "required": [
        "device_id",
        "level"
      ],
      "title": "SetLevel",
      "type": "object"
    },
    "SetTarget": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "set_target",
          "default": "set_target",
          "title": "Kind",
          "type": "string"
        },
        "target": {
          "enum": [
            "heating_day",
            "heating_night"
          ],
          "title": "Target",
          "type": "string"
        },
        "value_c": {
          "maximum": 40,
          "minimum": 0,
          "title": "Value C",
          "type": "number"
        }
      },
      "required": [
        "target",
        "value_c"
      ],
      "title": "SetTarget",
      "type": "object"
    },
    "Timing": {
      "oneOf": [
        {
          "$ref": "#/$defs/At"
        },
        {
          "$ref": "#/$defs/Window"
        },
        {
          "$ref": "#/$defs/Asap"
        }
      ]
    },
    "Water": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "water",
          "default": "water",
          "title": "Kind",
          "type": "string"
        },
        "plant_id": {
          "$ref": "#/$defs/ItemName"
        },
        "amount_ml": {
          "exclusiveMinimum": 0,
          "maximum": 2000,
          "title": "Amount Ml",
          "type": "number"
        }
      },
      "required": [
        "plant_id",
        "amount_ml"
      ],
      "title": "Water",
      "type": "object"
    },
    "Window": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "window",
          "default": "window",
          "title": "Kind",
          "type": "string"
        },
        "not_before": {
          "$ref": "#/$defs/Instant"
        },
        "not_after": {
          "$ref": "#/$defs/Instant"
        }
      },
      "required": [
        "not_before",
        "not_after"
      ],
      "title": "Window",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "plan_id": {
      "$ref": "#/$defs/Identifier"
    },
    "run_id": {
      "$ref": "#/$defs/Name"
    },
    "epoch": {
      "minimum": 0,
      "title": "Epoch",
      "type": "integer"
    },
    "revision": {
      "minimum": 1,
      "title": "Revision",
      "type": "integer"
    },
    "actions": {
      "items": {
        "$ref": "#/$defs/PlannedAction"
      },
      "title": "Actions",
      "type": "array"
    }
  },
  "required": [
    "plan_id",
    "run_id",
    "epoch",
    "revision",
    "actions"
  ],
  "title": "Plan",
  "type": "object"
};
