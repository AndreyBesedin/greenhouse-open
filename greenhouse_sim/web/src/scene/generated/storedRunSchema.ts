// Generated from greenhouse_sim/services/stored_run.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const STORED_RUN_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
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
  "additionalProperties": false,
  "description": "An epoch as a person's list shows it: which run, whose seed, in what\nstate, and how far it is committed.",
  "properties": {
    "run_id": {
      "title": "Run Id",
      "type": "string"
    },
    "epoch": {
      "title": "Epoch",
      "type": "integer"
    },
    "scenario_id": {
      "title": "Scenario Id",
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
    "layout": {
      "title": "Layout",
      "type": "string"
    },
    "status": {
      "$ref": "#/$defs/Status"
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
    "progress": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Progress"
    },
    "created_at": {
      "anyOf": [
        {
          "format": "date-time",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Created At"
    },
    "size_bytes": {
      "title": "Size Bytes",
      "type": "integer"
    }
  },
  "required": [
    "run_id",
    "epoch",
    "scenario_id",
    "seed",
    "layout",
    "status",
    "frontier_s",
    "duration_s",
    "progress",
    "created_at",
    "size_bytes"
  ],
  "title": "StoredRun",
  "type": "object"
};
