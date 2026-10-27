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
      "description": "As soon as what it waits for is done, before its deadline if it has\none.",
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
      "description": "Due at an instant.",
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
      "description": "Who carries an action out: a kind of executor, and which one, or any\nof the kind when `id` is None.",
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
      "description": "Lower a plant's stem: by so many centimetres, by so many internodes,\nor until its top has so much head room under its wire. Exactly one.",
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
      "description": "What a gateway does with an action that cannot start by its due\ninstant and tolerance.",
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
      "description": "Who asks for an action, by identity: a person, a control policy, a\nschedule, a scenario's own plan, a platform.",
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
      "description": "Every `period`, `count` times or until an instant: occurrence `n`,\nfrom 0, is the planned action's timing moved by `n` periods. The timing\nis its one anchor.",
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
      "description": "A device's level, from 0 (off) to 1 (full), or `auto` to hand the\ndevice back to whatever control loop runs it. A door or vent is a\ndevice, its level how far it is open.",
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
      "description": "A climate controller's heating setpoint, by day or by night, in °C.\nEach kind of target has its own unit and range: the venting and humidity\ntargets, when a controller has them, are members of their own beside\nthis one.",
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
      "description": "Due between two instants: it starts at the earliest one in them an\nexecutor can honour and is free to take.",
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
  "description": "The actions a run is to carry out, given in one of its epochs as one\nrevision of a plan. A revision replaces, from an instant on, the actions\nof the one before that have not started (the gateway's rule).\n\nChecked as made: action ids unique, every prerequisite in the plan, no\ncycle. Edges between recurring actions pair their occurrences, so two\nrecurring actions may wait for one another only if they recur alike,\noccurrence `n` for occurrence `n`; a recurring action may wait for a\none-off one, each occurrence for it; a one-off action may not wait for a\nrecurring one, since which occurrence is meant is not said. With those\nedges the plan, expanded occurrence by occurrence, has a cycle only if it\nhas one as given, so it is checked as given.",
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
