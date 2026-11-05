// Generated from greenhouse_sim/climate/probes.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const CLIMATE_PROBES_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ProbeSeries": {
      "additionalProperties": false,
      "properties": {
        "point": {
          "$ref": "#/$defs/Vector3"
        },
        "controlled": {
          "$ref": "#/$defs/Readings"
        },
        "all_off": {
          "$ref": "#/$defs/Readings"
        }
      },
      "required": [
        "point",
        "controlled",
        "all_off"
      ],
      "title": "ProbeSeries",
      "type": "object"
    },
    "Readings": {
      "additionalProperties": false,
      "properties": {
        "temperature_c": {
          "items": {
            "type": "number"
          },
          "title": "Temperature C",
          "type": "array"
        },
        "humidity_pct": {
          "items": {
            "type": "number"
          },
          "title": "Humidity Pct",
          "type": "array"
        },
        "speed_m_s": {
          "items": {
            "type": "number"
          },
          "title": "Speed M S",
          "type": "array"
        }
      },
      "required": [
        "temperature_c",
        "humidity_pct",
        "speed_m_s"
      ],
      "title": "Readings",
      "type": "object"
    },
    "Vector3": {
      "properties": {
        "x": {
          "title": "X",
          "type": "number"
        },
        "y": {
          "title": "Y",
          "type": "number"
        },
        "z": {
          "title": "Z",
          "type": "number"
        }
      },
      "required": [
        "x",
        "y",
        "z"
      ],
      "title": "Vector3",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "times_s": {
      "items": {
        "type": "number"
      },
      "title": "Times S",
      "type": "array"
    },
    "probes": {
      "items": {
        "$ref": "#/$defs/ProbeSeries"
      },
      "title": "Probes",
      "type": "array"
    }
  },
  "required": [
    "times_s",
    "probes"
  ],
  "title": "ClimateProbes",
  "type": "object"
};
