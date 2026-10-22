// Generated from greenhouse_sim/services/field_names.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const FIELD_NAMES_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "The fields a scenario offers with one of its layouts, its own airflow\nfirst, and the name of its own airflow.",
  "properties": {
    "fields": {
      "items": {
        "type": "string"
      },
      "title": "Fields",
      "type": "array"
    },
    "configured": {
      "title": "Configured",
      "type": "string"
    }
  },
  "required": [
    "fields",
    "configured"
  ],
  "title": "FieldNames",
  "type": "object"
};
