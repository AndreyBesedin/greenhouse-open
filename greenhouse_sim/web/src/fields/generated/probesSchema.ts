// Generated from greenhouse_sim/climate/probes.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const CLIMATE_PROBES_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ProbeSeries": {
      "additionalProperties": false,
      "description": "A probe's point, and what it reads through the run and through the\nsame run with everything off.",
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
      "description": "A probe's readings at each moment: temperature (°C), relative humidity\n(%) and air speed (m/s).",
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
  "description": "Probes through a climate run, at each of its moments, in seconds.",
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
