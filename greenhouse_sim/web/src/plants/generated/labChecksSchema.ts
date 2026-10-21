// Generated from greenhouse_sim/services/lab_checks.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const LAB_CHECKS_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "description": "Whatever is wrong with each of the lab's plants on a run's day.",
  "properties": {
    "day": {
      "title": "Day",
      "type": "integer"
    },
    "problems": {
      "additionalProperties": {
        "items": {
          "type": "string"
        },
        "type": "array"
      },
      "title": "Problems",
      "type": "object"
    }
  },
  "required": [
    "day",
    "problems"
  ],
  "title": "LabChecks",
  "type": "object"
};
