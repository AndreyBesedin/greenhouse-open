// Generated from greenhouse_sim/cfd/geometry.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const CFD_GEOMETRY_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "Boundary": {
      "additionalProperties": false,
      "description": "One boundary of the domain as it is meshed: what it is, and the faces\nof the mesh it is made of.",
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "category": {
          "$ref": "#/$defs/BoundaryCategory"
        },
        "face": {
          "anyOf": [
            {
              "$ref": "#/$defs/Face"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "opening_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Opening Id"
        },
        "opening_kind": {
          "anyOf": [
            {
              "$ref": "#/$defs/OpeningKind"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "box": {
          "$ref": "#/$defs/Box"
        },
        "mesh_faces": {
          "title": "Mesh Faces",
          "type": "integer"
        }
      },
      "required": [
        "name",
        "category",
        "box",
        "mesh_faces"
      ],
      "title": "Boundary",
      "type": "object"
    },
    "BoundaryCategory": {
      "description": "What a boundary of the CFD domain is.",
      "enum": [
        "floor",
        "wall",
        "ceiling",
        "opening",
        "obstacle"
      ],
      "title": "BoundaryCategory",
      "type": "string"
    },
    "Box": {
      "additionalProperties": false,
      "description": "An axis-aligned box, by its lowest and highest corners.",
      "properties": {
        "minimum": {
          "$ref": "#/$defs/Vector3"
        },
        "maximum": {
          "$ref": "#/$defs/Vector3"
        }
      },
      "required": [
        "minimum",
        "maximum"
      ],
      "title": "Box",
      "type": "object"
    },
    "CellCounts": {
      "additionalProperties": false,
      "description": "How many cells a grid has along x, y and z.",
      "properties": {
        "x": {
          "exclusiveMinimum": 0,
          "title": "X",
          "type": "integer"
        },
        "y": {
          "exclusiveMinimum": 0,
          "title": "Y",
          "type": "integer"
        },
        "z": {
          "exclusiveMinimum": 0,
          "title": "Z",
          "type": "integer"
        }
      },
      "required": [
        "x",
        "y",
        "z"
      ],
      "title": "CellCounts",
      "type": "object"
    },
    "Face": {
      "description": "One of the domain's six faces, by where it lies.",
      "enum": [
        "floor",
        "ceiling",
        "wall_front",
        "wall_back",
        "wall_right",
        "wall_left"
      ],
      "title": "Face",
      "type": "string"
    },
    "FieldGrid": {
      "additionalProperties": false,
      "description": "A box divided into a regular grid of cells.",
      "properties": {
        "origin": {
          "$ref": "#/$defs/Vector3"
        },
        "cell_size": {
          "$ref": "#/$defs/Vector3"
        },
        "cells": {
          "$ref": "#/$defs/CellCounts"
        }
      },
      "required": [
        "origin",
        "cell_size",
        "cells"
      ],
      "title": "FieldGrid",
      "type": "object"
    },
    "OpeningKind": {
      "enum": [
        "door",
        "roof_vent",
        "side_vent"
      ],
      "title": "OpeningKind",
      "type": "string"
    },
    "Vector3": {
      "properties": {
        "x": {
          "title": "X",
          "type": "number"
        },
        "y": {
          "title": "Y",
          "type": "number"
        },
        "z": {
          "title": "Z",
          "type": "number"
        }
      },
      "required": [
        "x",
        "y",
        "z"
      ],
      "title": "Vector3",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "What a solver is given for a scenario: the domain, on its grid, and\nevery boundary, as they will be meshed.",
  "properties": {
    "schema_version": {
      "const": 1,
      "default": 1,
      "title": "Schema Version",
      "type": "integer"
    },
    "scenario_id": {
      "title": "Scenario Id",
      "type": "string"
    },
    "grid": {
      "$ref": "#/$defs/FieldGrid"
    },
    "boundaries": {
      "items": {
        "$ref": "#/$defs/Boundary"
      },
      "title": "Boundaries",
      "type": "array"
    },
    "too_small": {
      "items": {
        "type": "string"
      },
      "title": "Too Small",
      "type": "array"
    },
    "unplaced": {
      "items": {
        "type": "string"
      },
      "title": "Unplaced",
      "type": "array"
    }
  },
  "required": [
    "scenario_id",
    "grid",
    "boundaries",
    "too_small",
    "unplaced"
  ],
  "title": "CfdGeometry",
  "type": "object"
};
