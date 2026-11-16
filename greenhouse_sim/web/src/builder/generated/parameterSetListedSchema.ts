// Generated from greenhouse_sim/services/parameter_set_listed.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const PARAMETER_SET_LISTED_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
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
    "model": {
      "title": "Model",
      "type": "string"
    },
    "name": {
      "title": "Name",
      "type": "string"
    },
    "version": {
      "title": "Version",
      "type": "integer"
    },
    "digest": {
      "title": "Digest",
      "type": "string"
    },
    "based_on": {
      "anyOf": [
        {
          "$ref": "#/$defs/SetNamed"
        },
        {
          "type": "null"
        }
      ]
    },
    "made_for": {
      "title": "Made For",
      "type": "integer"
    },
    "cultivar": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Cultivar"
    },
    "description": {
      "title": "Description",
      "type": "string"
    },
    "published": {
      "title": "Published",
      "type": "boolean"
    }
  },
  "required": [
    "model",
    "name",
    "version",
    "digest",
    "based_on",
    "made_for",
    "cultivar",
    "description",
    "published"
  ],
  "title": "SetListed",
  "type": "object"
};
