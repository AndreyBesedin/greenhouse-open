// Generated from greenhouse_sim/services/version.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const VERSION_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "properties": {
    "simulator": {
      "title": "Simulator",
      "type": "string"
    },
    "version": {
      "title": "Version",
      "type": "string"
    },
    "commit": {
      "title": "Commit",
      "type": "string"
    },
    "scene_schema_version": {
      "title": "Scene Schema Version",
      "type": "integer"
    }
  },
  "required": [
    "simulator",
    "version",
    "commit",
    "scene_schema_version"
  ],
  "title": "Version",
  "type": "object"
};
