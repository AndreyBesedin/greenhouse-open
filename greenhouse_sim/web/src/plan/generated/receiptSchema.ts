// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/receipt.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const RECEIPT_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ActionId": {
      "minLength": 1,
      "pattern": "^[A-Za-z0-9_.-]+$",
      "type": "string"
    },
    "ActionKey": {
      "additionalProperties": false,
      "description": "An action as a caller saw it, to cancel it: in a plan, a revision and\nan epoch. A key whose action a later revision replaced, or whose epoch\nhas ended, is stale: refused, and nothing cancelled. An occurrence of\nNone, for a recurring action, means every occurrence still to come.",
      "properties": {
        "plan_id": {
          "$ref": "#/$defs/Identifier"
        },
        "epoch": {
          "minimum": 0,
          "title": "Epoch",
          "type": "integer"
        },
        "revision": {
          "minimum": 1,
          "title": "Revision",
          "type": "integer"
        },
        "ref": {
          "$ref": "#/$defs/ActionRef"
        }
      },
      "required": [
        "plan_id",
        "epoch",
        "revision",
        "ref"
      ],
      "title": "ActionKey",
      "type": "object"
    },
    "ActionRef": {
      "additionalProperties": false,
      "description": "Which action a record is about: a planned action, one occurrence of a\nrecurring one, or the fallback carried out in its place. `str()` spells\nit for people, `harvest@3` or `vent/fallback`; records keep the parts.",
      "properties": {
        "action_id": {
          "$ref": "#/$defs/ActionId"
        },
        "occurrence": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Occurrence"
        },
        "fallback": {
          "default": false,
          "title": "Fallback",
          "type": "boolean"
        }
      },
      "required": [
        "action_id"
      ],
      "title": "ActionRef",
      "type": "object"
    },
    "Identifier": {
      "minLength": 1,
      "pattern": "^[A-Za-z0-9_.-]+$",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "description": "A gateway's answer to a write. A request refused whole has its\nerrors and changed nothing; one accepted lists what it refused at once,\nwhat it cancelled, and the keys it would not act on.",
  "properties": {
    "accepted": {
      "title": "Accepted",
      "type": "boolean"
    },
    "plan_id": {
      "anyOf": [
        {
          "$ref": "#/$defs/Identifier"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "revision": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Revision"
    },
    "sequence": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Sequence"
    },
    "errors": {
      "default": [],
      "items": {
        "type": "string"
      },
      "title": "Errors",
      "type": "array"
    },
    "refused": {
      "default": [],
      "items": {
        "$ref": "#/$defs/ActionRef"
      },
      "title": "Refused",
      "type": "array"
    },
    "cancelled": {
      "default": [],
      "items": {
        "$ref": "#/$defs/ActionRef"
      },
      "title": "Cancelled",
      "type": "array"
    },
    "stale": {
      "default": [],
      "items": {
        "$ref": "#/$defs/ActionKey"
      },
      "title": "Stale",
      "type": "array"
    },
    "not_permitted": {
      "default": [],
      "items": {
        "$ref": "#/$defs/ActionKey"
      },
      "title": "Not Permitted",
      "type": "array"
    }
  },
  "required": [
    "accepted"
  ],
  "title": "Receipt",
  "type": "object"
};
