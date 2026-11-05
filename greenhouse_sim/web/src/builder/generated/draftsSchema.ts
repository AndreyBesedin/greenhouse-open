// Generated from greenhouse_sim/services/drafts.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const DRAFTS_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "DraftListed": {
      "properties": {
        "draft_id": {
          "title": "Draft Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "saved_at": {
          "format": "date-time",
          "title": "Saved At",
          "type": "string"
        }
      },
      "required": [
        "draft_id",
        "name",
        "revision",
        "saved_at"
      ],
      "title": "DraftListed",
      "type": "object"
    }
  },
  "items": {
    "$ref": "#/$defs/DraftListed"
  },
  "type": "array"
};
