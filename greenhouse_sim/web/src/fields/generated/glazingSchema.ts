// Generated from greenhouse_sim/climate/glazing.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const GLAZING_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "SurfaceTemperature": {
      "additionalProperties": false,
      "properties": {
        "surface_id": {
          "title": "Surface Id",
          "type": "string"
        },
        "air_c": {
          "title": "Air C",
          "type": "number"
        },
        "surface_c": {
          "title": "Surface C",
          "type": "number"
        },
        "loss_w": {
          "title": "Loss W",
          "type": "number"
        }
      },
      "required": [
        "surface_id",
        "air_c",
        "surface_c",
        "loss_w"
      ],
      "title": "SurfaceTemperature",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "outside_c": {
      "title": "Outside C",
      "type": "number"
    },
    "u_w_m2k": {
      "title": "U W M2K",
      "type": "number"
    },
    "surfaces": {
      "items": {
        "$ref": "#/$defs/SurfaceTemperature"
      },
      "title": "Surfaces",
      "type": "array"
    }
  },
  "required": [
    "time_s",
    "outside_c",
    "u_w_m2k",
    "surfaces"
  ],
  "title": "GlazingAt",
  "type": "object"
};
