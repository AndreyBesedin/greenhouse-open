// Generated from greenhouse_sim/climate/openings.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const OPENINGS_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "OpeningFlow": {
      "additionalProperties": false,
      "description": "What an open door or vent passes: its net flow into the house (m³/s,\nnegative out), and what it exchanges each way besides.",
      "properties": {
        "opening_id": {
          "title": "Opening Id",
          "type": "string"
        },
        "net_m3_s": {
          "title": "Net M3 S",
          "type": "number"
        },
        "exchange_m3_s": {
          "title": "Exchange M3 S",
          "type": "number"
        }
      },
      "required": [
        "opening_id",
        "net_m3_s",
        "exchange_m3_s"
      ],
      "title": "OpeningFlow",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "What each open door and vent passes at a moment of a run.",
  "properties": {
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "openings": {
      "items": {
        "$ref": "#/$defs/OpeningFlow"
      },
      "title": "Openings",
      "type": "array"
    }
  },
  "required": [
    "time_s",
    "openings"
  ],
  "title": "OpeningsAt",
  "type": "object"
};
