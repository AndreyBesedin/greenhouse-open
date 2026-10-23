// Generated from greenhouse_sim/builder/basic.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const BASIC_SETUP_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "CropModel": {
      "description": "How a scenario's run grows its crop: by the simple daily model,\nthrough the engine, or organ by organ (`greenhouse_sim.core.crop`).",
      "enum": [
        "simple",
        "organ"
      ],
      "title": "CropModel",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "description": "The values of the builder's first form, in metres. Each field's title\nis the form's label for it, and the schema's example the house the form\nstarts from. Each is checked as the envelope and the rows check what it\nbecomes, before either is made, so that a value refused is refused by\nthe form's own field: their bounds, and their rules between two values,\nheld by the second.",
  "examples": [
    {
      "bays": 3,
      "crop_model": "simple",
      "eave_height_m": 4,
      "installation_id": "my_greenhouse",
      "length_m": 12,
      "name": "My greenhouse",
      "plant_pitch_m": 0.5,
      "plants_per_row": 16,
      "ridge_height_m": 4.8,
      "row_spacing_m": 1.6,
      "rows": 2,
      "spans": 1,
      "support_height_m": 0.3,
      "variety": "cherry_tomato",
      "width_m": 6.4
    }
  ],
  "properties": {
    "installation_id": {
      "description": "Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.",
      "pattern": "^[A-Za-z0-9_.-]+$",
      "title": "Identifier",
      "type": "string"
    },
    "name": {
      "minLength": 1,
      "title": "Name",
      "type": "string"
    },
    "length_m": {
      "exclusiveMinimum": 0,
      "maximum": 500,
      "title": "Length (m)",
      "type": "number"
    },
    "width_m": {
      "exclusiveMinimum": 0,
      "maximum": 500,
      "title": "Width (m)",
      "type": "number"
    },
    "eave_height_m": {
      "exclusiveMinimum": 0,
      "maximum": 50,
      "title": "Height to the gutters (m)",
      "type": "number"
    },
    "ridge_height_m": {
      "exclusiveMinimum": 0,
      "maximum": 50,
      "title": "Height to the ridge (m)",
      "type": "number"
    },
    "spans": {
      "default": 1,
      "exclusiveMinimum": 0,
      "maximum": 100,
      "title": "Spans",
      "type": "integer"
    },
    "bays": {
      "default": 1,
      "exclusiveMinimum": 0,
      "maximum": 200,
      "title": "Bays",
      "type": "integer"
    },
    "rows": {
      "exclusiveMinimum": 0,
      "maximum": 1000,
      "title": "Crop rows",
      "type": "integer"
    },
    "plants_per_row": {
      "exclusiveMinimum": 0,
      "maximum": 10000,
      "title": "Plants per row",
      "type": "integer"
    },
    "plant_pitch_m": {
      "exclusiveMinimum": 0,
      "title": "Between plants (m)",
      "type": "number"
    },
    "row_spacing_m": {
      "exclusiveMinimum": 0,
      "title": "Between rows (m)",
      "type": "number"
    },
    "support_height_m": {
      "exclusiveMinimum": 0.12,
      "title": "Gutter height (m)",
      "type": "number"
    },
    "crop_model": {
      "$ref": "#/$defs/CropModel",
      "title": "Crop model"
    },
    "variety": {
      "minLength": 1,
      "title": "Variety",
      "type": "string"
    }
  },
  "required": [
    "installation_id",
    "name",
    "length_m",
    "width_m",
    "eave_height_m",
    "ridge_height_m",
    "rows",
    "plants_per_row",
    "plant_pitch_m",
    "row_spacing_m",
    "support_height_m",
    "crop_model",
    "variety"
  ],
  "title": "BasicSetup",
  "type": "object"
};
