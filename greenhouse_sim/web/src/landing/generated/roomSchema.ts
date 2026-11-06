// Generated from greenhouse_sim/services/room.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const ROOM_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "properties": {
    "workers_busy": {
      "title": "Workers Busy",
      "type": "integer"
    },
    "workers_limit": {
      "title": "Workers Limit",
      "type": "integer"
    },
    "runs_waiting": {
      "title": "Runs Waiting",
      "type": "integer"
    },
    "runs_waiting_limit": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Runs Waiting Limit"
    },
    "disk_free_bytes": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Disk Free Bytes"
    },
    "disk_free_limit_bytes": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Disk Free Limit Bytes"
    },
    "refusal": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Refusal"
    }
  },
  "required": [
    "workers_busy",
    "workers_limit",
    "runs_waiting",
    "runs_waiting_limit",
    "disk_free_bytes",
    "disk_free_limit_bytes",
    "refusal"
  ],
  "title": "Room",
  "type": "object"
};
