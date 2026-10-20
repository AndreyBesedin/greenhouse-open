// Generated from greenhouse_sim/services/timeline.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const TIMELINE_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "A run's events from `from_s` to `until_s`, in the order they happen,\ncolumn by column.",
  "properties": {
    "from_s": {
      "title": "From S",
      "type": "number"
    },
    "until_s": {
      "title": "Until S",
      "type": "number"
    },
    "processes": {
      "items": {
        "type": "string"
      },
      "title": "Processes",
      "type": "array"
    },
    "subjects": {
      "items": {
        "type": "string"
      },
      "title": "Subjects",
      "type": "array"
    },
    "kinds": {
      "items": {
        "type": "string"
      },
      "title": "Kinds",
      "type": "array"
    },
    "times_s": {
      "items": {
        "type": "number"
      },
      "title": "Times S",
      "type": "array"
    },
    "process": {
      "items": {
        "type": "integer"
      },
      "title": "Process",
      "type": "array"
    },
    "subject": {
      "items": {
        "type": "integer"
      },
      "title": "Subject",
      "type": "array"
    },
    "kind": {
      "items": {
        "type": "integer"
      },
      "title": "Kind",
      "type": "array"
    }
  },
  "required": [
    "from_s",
    "until_s",
    "processes",
    "subjects",
    "kinds",
    "times_s",
    "process",
    "subject",
    "kind"
  ],
  "title": "TimelineDocument",
  "type": "object"
};
