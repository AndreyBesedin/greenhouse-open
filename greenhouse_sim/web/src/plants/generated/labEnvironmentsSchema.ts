// Generated from greenhouse_sim/services/lab_environments.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const LAB_ENVIRONMENTS_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "LocalEnvironment": {
      "additionalProperties": false,
      "description": "What one plant experiences over one day, where it stands.",
      "properties": {
        "mean_temperature_c": {
          "title": "Mean Temperature C",
          "type": "number"
        },
        "par_mol_m2_day": {
          "minimum": 0,
          "title": "Par Mol M2 Day",
          "type": "number"
        },
        "co2_ppm": {
          "minimum": 0,
          "title": "Co2 Ppm",
          "type": "number"
        },
        "water_status": {
          "default": 1,
          "maximum": 1,
          "minimum": 0,
          "title": "Water Status",
          "type": "number"
        }
      },
      "required": [
        "mean_temperature_c",
        "par_mol_m2_day",
        "co2_ppm",
        "water_status"
      ],
      "title": "LocalEnvironment",
      "type": "object"
    }
  },
  "additionalProperties": {
    "$ref": "#/$defs/LocalEnvironment"
  },
  "type": "object"
};
