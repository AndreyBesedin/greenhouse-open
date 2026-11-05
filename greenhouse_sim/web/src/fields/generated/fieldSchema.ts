// Generated from greenhouse_sim/fields/field.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const FIELD_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "AirQuantity": {
      "enum": [
        "velocity",
        "temperature",
        "humidity",
        "co2",
        "pressure",
        "par",
        "irradiance"
      ],
      "title": "AirQuantity",
      "type": "string"
    },
    "CellCounts": {
      "additionalProperties": false,
      "properties": {
        "x": {
          "exclusiveMinimum": 0,
          "title": "X",
          "type": "integer"
        },
        "y": {
          "exclusiveMinimum": 0,
          "title": "Y",
          "type": "integer"
        },
        "z": {
          "exclusiveMinimum": 0,
          "title": "Z",
          "type": "integer"
        }
      },
      "required": [
        "x",
        "y",
        "z"
      ],
      "title": "CellCounts",
      "type": "object"
    },
    "ChannelDocument": {
      "additionalProperties": false,
      "properties": {
        "quantity": {
          "$ref": "#/$defs/AirQuantity"
        },
        "unit": {
          "title": "Unit",
          "type": "string"
        },
        "components": {
          "enum": [
            1,
            3
          ],
          "title": "Components",
          "type": "integer"
        },
        "encoding": {
          "const": "float32-le-base64",
          "default": "float32-le-base64",
          "title": "Encoding",
          "type": "string"
        },
        "data": {
          "title": "Data",
          "type": "string"
        },
        "minimum": {
          "title": "Minimum",
          "type": "number"
        },
        "maximum": {
          "title": "Maximum",
          "type": "number"
        }
      },
      "required": [
        "quantity",
        "unit",
        "components",
        "data",
        "minimum",
        "maximum"
      ],
      "title": "ChannelDocument",
      "type": "object"
    },
    "FieldGrid": {
      "additionalProperties": false,
      "properties": {
        "origin": {
          "$ref": "#/$defs/Vector3"
        },
        "cell_size": {
          "$ref": "#/$defs/Vector3"
        },
        "cells": {
          "$ref": "#/$defs/CellCounts"
        }
      },
      "required": [
        "origin",
        "cell_size",
        "cells"
      ],
      "title": "FieldGrid",
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
    "schema_version": {
      "const": 1,
      "default": 1,
      "title": "Schema Version",
      "type": "integer"
    },
    "field_id": {
      "title": "Field Id",
      "type": "string"
    },
    "source": {
      "title": "Source",
      "type": "string"
    },
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "grid": {
      "$ref": "#/$defs/FieldGrid"
    },
    "channels": {
      "items": {
        "$ref": "#/$defs/ChannelDocument"
      },
      "title": "Channels",
      "type": "array"
    }
  },
  "required": [
    "schema_version",
    "field_id",
    "source",
    "time_s",
    "grid",
    "channels"
  ],
  "title": "FieldDocument",
  "type": "object"
};
