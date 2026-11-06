// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/plan-state.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const PLAN_STATE_SCHEMA = {
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
    "ActionState": {
      "additionalProperties": false,
      "properties": {
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
          "default": null,
          "title": "Due"
        },
        "principal": {
          "$ref": "#/$defs/Principal"
        },
        "state": {
          "$ref": "#/$defs/ActionStateKind"
        },
        "waiting_for": {
          "default": [],
          "items": {
            "$ref": "#/$defs/ActionRef"
          },
          "title": "Waiting For",
          "type": "array"
        },
        "waited_on_by": {
          "default": [],
          "items": {
            "$ref": "#/$defs/ActionRef"
          },
          "title": "Waited On By",
          "type": "array"
        },
        "carried_from": {
          "anyOf": [
            {
              "$ref": "#/$defs/RunEpoch"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "plan_id",
        "revision",
        "ref",
        "action",
        "timing",
        "principal",
        "state"
      ],
      "title": "ActionState",
      "type": "object"
    },
    "ActionStateKind": {
      "enum": [
        "waiting",
        "due",
        "assigned",
        "started"
      ],
      "title": "ActionStateKind",
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
    "AuthorisationChange": {
      "additionalProperties": false,
      "properties": {
        "version": {
          "minimum": 1,
          "title": "Version",
          "type": "integer"
        },
        "at": {
          "$ref": "#/$defs/Instant"
        }
      },
      "required": [
        "version",
        "at"
      ],
      "title": "AuthorisationChange",
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
    "Plan": {
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
    "RunEpoch": {
      "additionalProperties": false,
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
        }
      },
      "required": [
        "run_id",
        "epoch"
      ],
      "title": "RunEpoch",
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
    "plan": {
      "$ref": "#/$defs/Plan"
    },
    "owner": {
      "$ref": "#/$defs/Principal"
    },
    "sequence": {
      "minimum": 1,
      "title": "Sequence",
      "type": "integer"
    },
    "unresolved": {
      "items": {
        "$ref": "#/$defs/ActionState"
      },
      "title": "Unresolved",
      "type": "array"
    },
    "outcomes": {
      "items": {
        "$ref": "#/$defs/ActionOutcome"
      },
      "title": "Outcomes",
      "type": "array"
    },
    "authorisation": {
      "items": {
        "$ref": "#/$defs/AuthorisationChange"
      },
      "title": "Authorisation",
      "type": "array"
    }
  },
  "required": [
    "plan",
    "owner",
    "sequence",
    "unresolved",
    "outcomes",
    "authorisation"
  ],
  "title": "PlanState",
  "type": "object"
};
