// Generated from greenhouse_sim/services/position.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const POSITION_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ForkOf": {
      "additionalProperties": false,
      "properties": {
        "run_id": {
          "title": "Run Id",
          "type": "string"
        },
        "epoch": {
          "title": "Epoch",
          "type": "integer"
        },
        "at_s": {
          "title": "At S",
          "type": "number"
        },
        "start_s": {
          "title": "Start S",
          "type": "number"
        },
        "digest": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Digest"
        },
        "checkpoint_sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Checkpoint Sha256"
        },
        "inherited": {
          "default": 0,
          "title": "Inherited",
          "type": "integer"
        },
        "layout": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Layout"
        }
      },
      "required": [
        "run_id",
        "epoch",
        "at_s",
        "start_s",
        "digest",
        "checkpoint_sha256",
        "inherited",
        "layout"
      ],
      "title": "ForkOf",
      "type": "object"
    },
    "Status": {
      "enum": [
        "queued",
        "running",
        "finished",
        "failed",
        "interrupted"
      ],
      "title": "Status",
      "type": "string"
    }
  },
  "properties": {
    "position_id": {
      "title": "Position Id",
      "type": "string"
    },
    "scenario_id": {
      "title": "Scenario Id",
      "type": "string"
    },
    "run_id": {
      "title": "Run Id",
      "type": "string"
    },
    "epoch": {
      "title": "Epoch",
      "type": "integer"
    },
    "layout": {
      "title": "Layout",
      "type": "string"
    },
    "seed": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Seed"
    },
    "weather": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Weather"
    },
    "status": {
      "$ref": "#/$defs/Status"
    },
    "started_at": {
      "format": "date-time",
      "title": "Started At",
      "type": "string"
    },
    "simulated_now": {
      "format": "date-time",
      "title": "Simulated Now",
      "type": "string"
    },
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "day": {
      "title": "Day",
      "type": "integer"
    },
    "playing": {
      "title": "Playing",
      "type": "boolean"
    },
    "following": {
      "title": "Following",
      "type": "boolean"
    },
    "seconds_per_day": {
      "title": "Seconds Per Day",
      "type": "number"
    },
    "frontier_s": {
      "title": "Frontier S",
      "type": "number"
    },
    "duration_s": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Duration S"
    },
    "start_s": {
      "default": 0,
      "title": "Start S",
      "type": "number"
    },
    "fork": {
      "anyOf": [
        {
          "$ref": "#/$defs/ForkOf"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "parent_kept": {
      "default": false,
      "title": "Parent Kept",
      "type": "boolean"
    },
    "targets": {
      "default": [],
      "items": {
        "maxItems": 3,
        "minItems": 3,
        "prefixItems": [
          {
            "type": "number"
          },
          {
            "type": "string"
          },
          {
            "type": "number"
          }
        ],
        "type": "array"
      },
      "title": "Targets",
      "type": "array"
    },
    "commands": {
      "default": [],
      "items": {
        "maxItems": 3,
        "minItems": 3,
        "prefixItems": [
          {
            "type": "number"
          },
          {
            "type": "string"
          },
          {
            "type": "number"
          }
        ],
        "type": "array"
      },
      "title": "Commands",
      "type": "array"
    },
    "crop": {
      "default": [],
      "items": {
        "maxItems": 4,
        "minItems": 4,
        "prefixItems": [
          {
            "type": "number"
          },
          {
            "type": "string"
          },
          {
            "type": "string"
          },
          {
            "type": "string"
          }
        ],
        "type": "array"
      },
      "title": "Crop",
      "type": "array"
    }
  },
  "required": [
    "position_id",
    "scenario_id",
    "run_id",
    "epoch",
    "layout",
    "seed",
    "weather",
    "status",
    "started_at",
    "simulated_now",
    "time_s",
    "day",
    "playing",
    "following",
    "seconds_per_day",
    "frontier_s",
    "duration_s",
    "start_s",
    "fork",
    "parent_kept",
    "targets",
    "commands",
    "crop"
  ],
  "title": "PositionState",
  "type": "object"
};
