// Generated from greenhouse_sim/services/area_crop.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const AREA_CROP_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "AreaBasis": {
      "enum": [
        "floor",
        "cultivated"
      ],
      "title": "AreaBasis",
      "type": "string"
    },
    "AreaQuantity": {
      "properties": {
        "key": {
          "title": "Key",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "unit": {
          "title": "Unit",
          "type": "string"
        }
      },
      "required": [
        "key",
        "name",
        "unit"
      ],
      "title": "AreaQuantity",
      "type": "object"
    },
    "ScopeCourse": {
      "properties": {
        "scope_id": {
          "title": "Scope Id",
          "type": "string"
        },
        "area_m2": {
          "title": "Area M2",
          "type": "number"
        },
        "values": {
          "additionalProperties": {
            "items": {
              "type": "number"
            },
            "type": "array"
          },
          "title": "Values",
          "type": "object"
        }
      },
      "required": [
        "scope_id",
        "area_m2",
        "values"
      ],
      "title": "ScopeCourse",
      "type": "object"
    }
  },
  "properties": {
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "model": {
      "title": "Model",
      "type": "string"
    },
    "model_name": {
      "title": "Model Name",
      "type": "string"
    },
    "basis": {
      "$ref": "#/$defs/AreaBasis"
    },
    "quantities": {
      "items": {
        "$ref": "#/$defs/AreaQuantity"
      },
      "title": "Quantities",
      "type": "array"
    },
    "days": {
      "items": {
        "type": "integer"
      },
      "title": "Days",
      "type": "array"
    },
    "scopes": {
      "items": {
        "$ref": "#/$defs/ScopeCourse"
      },
      "title": "Scopes",
      "type": "array"
    },
    "house": {
      "additionalProperties": {
        "items": {
          "type": "number"
        },
        "type": "array"
      },
      "title": "House",
      "type": "object"
    }
  },
  "required": [
    "time_s",
    "model",
    "model_name",
    "basis",
    "quantities",
    "days",
    "scopes",
    "house"
  ],
  "title": "AreaCropCourse",
  "type": "object"
};
