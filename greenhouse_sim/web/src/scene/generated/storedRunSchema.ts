// Generated from greenhouse_sim/services/stored_run.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const STORED_RUN_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ForkOf": {
      "additionalProperties": false,
      "description": "Where a fork comes from (decision 0065): its parent, the exact instant\nit branches at, the state it inherits (a checkpoint at `start_s`, kept as a\ncopy of its own, and the parent's trajectory digest through it; none for\none from its run's start), how many entries of its log are its parent's,\nand the layout it changes to, if it does.",
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
    "paused": {
      "default": false,
      "title": "Paused",
      "type": "boolean"
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
    "damaged": {
      "default": false,
      "title": "Damaged",
      "type": "boolean"
    }
  },
  "required": [
    "run_id",
    "epoch",
    "scenario_id",
    "seed",
    "layout",
    "status",
    "paused",
    "frontier_s",
    "duration_s",
    "progress",
    "created_at",
    "size_bytes",
    "start_s",
    "fork",
    "damaged"
  ],
  "title": "StoredRun",
  "type": "object"
};
