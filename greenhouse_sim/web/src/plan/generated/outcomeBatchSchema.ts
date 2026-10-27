// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/outcome-batch.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const OUTCOME_BATCH_SCHEMA = {
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
    "ActionEffect": {
      "oneOf": [
        {
          "$ref": "#/$defs/LevelSet"
        },
        {
          "$ref": "#/$defs/TargetSet"
        },
        {
          "$ref": "#/$defs/Watered"
        },
        {
          "$ref": "#/$defs/Harvested"
        },
        {
          "$ref": "#/$defs/Lowered"
        },
        {
          "$ref": "#/$defs/LeafRemoved"
        },
        {
          "$ref": "#/$defs/Inspected"
        }
      ]
    },
    "ActionId": {
      "minLength": 1,
      "pattern": "^[A-Za-z0-9_.-]+$",
      "type": "string"
    },
    "ActionOutcome": {
      "additionalProperties": false,
      "description": "One planned action's end. Its fields agree with its status: an action\nthat ran has its times and its executor; one that never started has\nneither, and says why; only a cancelled or superseded one names who did\nit, only a missed one its fallback, only one that ran its effect, which\nis its action's kind's. `resolved_at`, when the outcome was decided, is\nalways set and orders the log; `due` is None only for an\nas-soon-as-possible action dropped before it could start.",
      "properties": {
        "outcome_id": {
          "$ref": "#/$defs/Identifier"
        },
        "greenhouse_id": {
          "$ref": "#/$defs/Name"
        },
        "run_id": {
          "$ref": "#/$defs/Name"
        },
        "epoch": {
          "minimum": 0,
          "title": "Epoch",
          "type": "integer"
        },
        "plan_id": {
          "$ref": "#/$defs/Identifier"
        },
        "revision": {
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "ref": {
          "$ref": "#/$defs/ActionRef"
        },
        "action": {
          "$ref": "#/$defs/Action"
        },
        "timing": {
          "$ref": "#/$defs/Timing"
        },
        "principal": {
          "$ref": "#/$defs/Principal"
        },
        "status": {
          "$ref": "#/$defs/OutcomeStatus"
        },
        "due": {
          "anyOf": [
            {
              "$ref": "#/$defs/Instant"
            },
            {
              "$ref": "#/$defs/Window"
            },
            {
              "type": "null"
            }
          ],
          "title": "Due"
        },
        "started_at": {
          "anyOf": [
            {
              "$ref": "#/$defs/Instant"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "finished_at": {
          "anyOf": [
            {
              "$ref": "#/$defs/Instant"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "resolved_at": {
          "$ref": "#/$defs/Instant"
        },
        "delivered_at": {
          "anyOf": [
            {
              "$ref": "#/$defs/Instant"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "executor": {
          "anyOf": [
            {
              "$ref": "#/$defs/ExecutorRef"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reason"
        },
        "cancelled_by": {
          "anyOf": [
            {
              "$ref": "#/$defs/Principal"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "fallback": {
          "anyOf": [
            {
              "$ref": "#/$defs/ActionRef"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "effect": {
          "anyOf": [
            {
              "$ref": "#/$defs/ActionEffect"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "event_id": {
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
        "outcome_id",
        "greenhouse_id",
        "run_id",
        "epoch",
        "plan_id",
        "revision",
        "ref",
        "action",
        "timing",
        "principal",
        "status",
        "due",
        "resolved_at"
      ],
      "title": "ActionOutcome",
      "type": "object"
    },
    "ActionRef": {
      "additionalProperties": false,
      "description": "Which action a record is about: a planned action, one occurrence of a\nrecurring one, or the fallback carried out in its place. `str()` spells\nit for people, `harvest@3` or `vent/fallback`; records keep the parts.",
      "properties": {
        "action_id": {
          "$ref": "#/$defs/ActionId"
        },
        "occurrence": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Occurrence"
        },
        "fallback": {
          "default": false,
          "title": "Fallback",
          "type": "boolean"
        }
      },
      "required": [
        "action_id"
      ],
      "title": "ActionRef",
      "type": "object"
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
    "Harvested": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "harvested",
          "default": "harvested",
          "title": "Kind",
          "type": "string"
        },
        "fruit_count": {
          "minimum": 0,
          "title": "Fruit Count",
          "type": "integer"
        },
        "fresh_mass_g": {
          "minimum": 0,
          "title": "Fresh Mass G",
          "type": "number"
        }
      },
      "required": [
        "fruit_count",
        "fresh_mass_g"
      ],
      "title": "Harvested",
      "type": "object"
    },
    "Identifier": {
      "minLength": 1,
      "pattern": "^[A-Za-z0-9_.-]+$",
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
    "Inspected": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "inspected",
          "default": "inspected",
          "title": "Kind",
          "type": "string"
        }
      },
      "title": "Inspected",
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
    "LeafRemoved": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "leaf_removed",
          "default": "leaf_removed",
          "title": "Kind",
          "type": "string"
        },
        "leaf_id": {
          "$ref": "#/$defs/Name"
        }
      },
      "required": [
        "leaf_id"
      ],
      "title": "LeafRemoved",
      "type": "object"
    },
    "LevelSet": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "level_set",
          "default": "level_set",
          "title": "Kind",
          "type": "string"
        },
        "device_id": {
          "$ref": "#/$defs/Name"
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
      "title": "LevelSet",
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
    "Lowered": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "lowered",
          "default": "lowered",
          "title": "Kind",
          "type": "string"
        },
        "by_cm": {
          "minimum": 0,
          "title": "By Cm",
          "type": "number"
        }
      },
      "required": [
        "by_cm"
      ],
      "title": "Lowered",
      "type": "object"
    },
    "Name": {
      "minLength": 1,
      "type": "string"
    },
    "OutcomeStatus": {
      "enum": [
        "executed",
        "late",
        "missed",
        "refused",
        "failed",
        "cancelled",
        "superseded",
        "unconfirmed"
      ],
      "title": "OutcomeStatus",
      "type": "string"
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
    "TargetSet": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "target_set",
          "default": "target_set",
          "title": "Kind",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/Name"
        },
        "value_c": {
          "title": "Value C",
          "type": "number"
        }
      },
      "required": [
        "target",
        "value_c"
      ],
      "title": "TargetSet",
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
    "Watered": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "watered",
          "default": "watered",
          "title": "Kind",
          "type": "string"
        },
        "amount_ml": {
          "minimum": 0,
          "title": "Amount Ml",
          "type": "number"
        }
      },
      "required": [
        "amount_ml"
      ],
      "title": "Watered",
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
  "description": "The outcomes delivered after a cursor, in delivery order.",
  "properties": {
    "run_id": {
      "minLength": 1,
      "title": "Run Id",
      "type": "string"
    },
    "epoch": {
      "minimum": 0,
      "title": "Epoch",
      "type": "integer"
    },
    "after": {
      "minimum": 0,
      "title": "After",
      "type": "integer"
    },
    "next": {
      "minimum": 0,
      "title": "Next",
      "type": "integer"
    },
    "simulated_now": {
      "$ref": "#/$defs/Instant"
    },
    "has_more": {
      "default": false,
      "title": "Has More",
      "type": "boolean"
    },
    "outcomes": {
      "items": {
        "$ref": "#/$defs/ActionOutcome"
      },
      "title": "Outcomes",
      "type": "array"
    }
  },
  "required": [
    "run_id",
    "epoch",
    "after",
    "next",
    "simulated_now",
    "outcomes"
  ],
  "title": "OutcomeBatch",
  "type": "object"
};
