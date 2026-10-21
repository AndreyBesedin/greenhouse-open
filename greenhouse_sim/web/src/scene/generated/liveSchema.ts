// Generated from greenhouse_sim/services/live.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const LIVE_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "Where a run stands: its frame's sequence, simulated day and instant,\nand whether it plays, and how fast.",
  "properties": {
    "sequence": {
      "title": "Sequence",
      "type": "integer"
    },
    "day": {
      "title": "Day",
      "type": "integer"
    },
    "timestamp": {
      "format": "date-time",
      "title": "Timestamp",
      "type": "string"
    },
    "playing": {
      "title": "Playing",
      "type": "boolean"
    },
    "speed": {
      "title": "Speed",
      "type": "number"
    }
  },
  "required": [
    "sequence",
    "day",
    "timestamp",
    "playing",
    "speed"
  ],
  "title": "LiveState",
  "type": "object"
};
