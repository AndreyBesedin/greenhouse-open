// Generated from greenhouse_sim/services/scenario_download.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const SCENARIO_DOWNLOAD_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "A scenario's file, for a client to offer as a download.",
  "properties": {
    "file_name": {
      "title": "File Name",
      "type": "string"
    },
    "text": {
      "title": "Text",
      "type": "string"
    },
    "has_recording": {
      "title": "Has Recording",
      "type": "boolean"
    }
  },
  "required": [
    "file_name",
    "text",
    "has_recording"
  ],
  "title": "ScenarioDownload",
  "type": "object"
};
