// Generated from greenhouse_sim/services/parameter_set_comparison.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const PARAMETER_SET_COMPARISON_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ParameterChange": {
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "first": {
          "title": "First",
          "type": "number"
        },
        "second": {
          "title": "Second",
          "type": "number"
        }
      },
      "required": [
        "name",
        "first",
        "second"
      ],
      "title": "ParameterChange",
      "type": "object"
    },
    "SetNamed": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "pattern": "^[a-z0-9][a-z0-9_]*$",
          "title": "Name",
          "type": "string"
        },
        "version": {
          "exclusiveMinimum": 0,
          "title": "Version",
          "type": "integer"
        },
        "digest": {
          "pattern": "^sha256:[0-9a-f]{64}$",
          "title": "Digest",
          "type": "string"
        }
      },
      "required": [
        "name",
        "version",
        "digest"
      ],
      "title": "SetNamed",
      "type": "object"
    }
  },
  "properties": {
    "first": {
      "$ref": "#/$defs/SetNamed"
    },
    "second": {
      "$ref": "#/$defs/SetNamed"
    },
    "changes": {
      "items": {
        "$ref": "#/$defs/ParameterChange"
      },
      "title": "Changes",
      "type": "array"
    }
  },
  "required": [
    "first",
    "second",
    "changes"
  ],
  "title": "SetComparison",
  "type": "object"
};
