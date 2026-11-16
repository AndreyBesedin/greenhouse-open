// Generated from greenhouse_sim/services/parameter_set_download.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const PARAMETER_SET_DOWNLOAD_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "properties": {
    "file_name": {
      "title": "File Name",
      "type": "string"
    },
    "text": {
      "title": "Text",
      "type": "string"
    }
  },
  "required": [
    "file_name",
    "text"
  ],
  "title": "SetDownload",
  "type": "object"
};
