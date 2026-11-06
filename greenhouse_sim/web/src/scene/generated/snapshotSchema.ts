// Generated from greenhouse_sim/scene/snapshot.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const SNAPSHOT_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "Axes": {
      "properties": {
        "shape": {
          "const": "axes",
          "default": "axes",
          "title": "Shape",
          "type": "string"
        },
        "length": {
          "exclusiveMinimum": 0,
          "title": "Length",
          "type": "number"
        }
      },
      "required": [
        "shape",
        "length"
      ],
      "title": "Axes",
      "type": "object"
    },
    "Box": {
      "properties": {
        "shape": {
          "const": "box",
          "default": "box",
          "title": "Shape",
          "type": "string"
        },
        "size_x": {
          "exclusiveMinimum": 0,
          "title": "Size X",
          "type": "number"
        },
        "size_y": {
          "exclusiveMinimum": 0,
          "title": "Size Y",
          "type": "number"
        },
        "size_z": {
          "exclusiveMinimum": 0,
          "title": "Size Z",
          "type": "number"
        }
      },
      "required": [
        "shape",
        "size_x",
        "size_y",
        "size_z"
      ],
      "title": "Box",
      "type": "object"
    },
    "Color": {
      "properties": {
        "r": {
          "maximum": 1,
          "minimum": 0,
          "title": "R",
          "type": "number"
        },
        "g": {
          "maximum": 1,
          "minimum": 0,
          "title": "G",
          "type": "number"
        },
        "b": {
          "maximum": 1,
          "minimum": 0,
          "title": "B",
          "type": "number"
        }
      },
      "required": [
        "r",
        "g",
        "b"
      ],
      "title": "Color",
      "type": "object"
    },
    "Cylinder": {
      "properties": {
        "shape": {
          "const": "cylinder",
          "default": "cylinder",
          "title": "Shape",
          "type": "string"
        },
        "radius": {
          "exclusiveMinimum": 0,
          "title": "Radius",
          "type": "number"
        },
        "height": {
          "minimum": 0,
          "title": "Height",
          "type": "number"
        }
      },
      "required": [
        "shape",
        "radius",
        "height"
      ],
      "title": "Cylinder",
      "type": "object"
    },
    "Ellipsoid": {
      "properties": {
        "shape": {
          "const": "ellipsoid",
          "default": "ellipsoid",
          "title": "Shape",
          "type": "string"
        },
        "size_x": {
          "exclusiveMinimum": 0,
          "title": "Size X",
          "type": "number"
        },
        "size_y": {
          "exclusiveMinimum": 0,
          "title": "Size Y",
          "type": "number"
        },
        "size_z": {
          "exclusiveMinimum": 0,
          "title": "Size Z",
          "type": "number"
        }
      },
      "required": [
        "shape",
        "size_x",
        "size_y",
        "size_z"
      ],
      "title": "Ellipsoid",
      "type": "object"
    },
    "Material": {
      "enum": [
        "steel",
        "aluminium",
        "plastic",
        "concrete",
        "substrate"
      ],
      "title": "Material",
      "type": "string"
    },
    "Plane": {
      "properties": {
        "shape": {
          "const": "plane",
          "default": "plane",
          "title": "Shape",
          "type": "string"
        },
        "size_x": {
          "exclusiveMinimum": 0,
          "title": "Size X",
          "type": "number"
        },
        "size_y": {
          "exclusiveMinimum": 0,
          "title": "Size Y",
          "type": "number"
        }
      },
      "required": [
        "shape",
        "size_x",
        "size_y"
      ],
      "title": "Plane",
      "type": "object"
    },
    "Point2": {
      "properties": {
        "x": {
          "title": "X",
          "type": "number"
        },
        "y": {
          "title": "Y",
          "type": "number"
        }
      },
      "required": [
        "x",
        "y"
      ],
      "title": "Point2",
      "type": "object"
    },
    "Polygon": {
      "properties": {
        "shape": {
          "const": "polygon",
          "default": "polygon",
          "title": "Shape",
          "type": "string"
        },
        "points": {
          "items": {
            "$ref": "#/$defs/Point2"
          },
          "minItems": 3,
          "title": "Points",
          "type": "array"
        }
      },
      "required": [
        "shape",
        "points"
      ],
      "title": "Polygon",
      "type": "object"
    },
    "Quaternion": {
      "properties": {
        "w": {
          "default": 1,
          "title": "W",
          "type": "number"
        },
        "x": {
          "default": 0,
          "title": "X",
          "type": "number"
        },
        "y": {
          "default": 0,
          "title": "Y",
          "type": "number"
        },
        "z": {
          "default": 0,
          "title": "Z",
          "type": "number"
        }
      },
      "required": [
        "w",
        "x",
        "y",
        "z"
      ],
      "title": "Quaternion",
      "type": "object"
    },
    "SceneEntity": {
      "properties": {
        "entity_id": {
          "title": "Entity Id",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/SceneEntityKind"
        },
        "transform": {
          "$ref": "#/$defs/Transform"
        },
        "shape": {
          "$ref": "#/$defs/Shape"
        },
        "color": {
          "$ref": "#/$defs/Color"
        },
        "material": {
          "anyOf": [
            {
              "$ref": "#/$defs/Material"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Label"
        },
        "properties": {
          "type": "object",
          "additionalProperties": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              },
              {
                "type": "number"
              },
              {
                "type": "boolean"
              }
            ]
          },
          "default": {},
          "title": "Properties"
        }
      },
      "required": [
        "entity_id",
        "kind",
        "transform",
        "shape",
        "color",
        "material",
        "label",
        "properties"
      ],
      "title": "SceneEntity",
      "type": "object"
    },
    "SceneEntityKind": {
      "enum": [
        "GROUND",
        "AXES",
        "GREENHOUSE_BOUNDS",
        "FLOOR",
        "WALL",
        "ROOF",
        "GUTTER",
        "FRAME",
        "VENT",
        "DOOR",
        "PLANTING_POSITION",
        "CROP_GUTTER",
        "BENCH",
        "SLAB",
        "WALKWAY",
        "SERVICE_ZONE",
        "KEEP_OUT",
        "RAIL",
        "PIPE",
        "WIRE",
        "OBSTACLE",
        "EQUIPMENT",
        "SENSOR",
        "CAMERA",
        "PLANT",
        "CANOPY",
        "INTERNODE",
        "LEAF",
        "TRUSS",
        "FLOWER",
        "FRUIT"
      ],
      "title": "SceneEntityKind",
      "type": "string"
    },
    "Shape": {
      "oneOf": [
        {
          "$ref": "#/$defs/Plane"
        },
        {
          "$ref": "#/$defs/Cylinder"
        },
        {
          "$ref": "#/$defs/Box"
        },
        {
          "$ref": "#/$defs/Polygon"
        },
        {
          "$ref": "#/$defs/Sphere"
        },
        {
          "$ref": "#/$defs/Ellipsoid"
        },
        {
          "$ref": "#/$defs/Axes"
        }
      ]
    },
    "Sphere": {
      "properties": {
        "shape": {
          "const": "sphere",
          "default": "sphere",
          "title": "Shape",
          "type": "string"
        },
        "radius": {
          "exclusiveMinimum": 0,
          "title": "Radius",
          "type": "number"
        }
      },
      "required": [
        "shape",
        "radius"
      ],
      "title": "Sphere",
      "type": "object"
    },
    "Transform": {
      "properties": {
        "position": {
          "$ref": "#/$defs/Vector3"
        },
        "rotation": {
          "$ref": "#/$defs/Quaternion",
          "default": {
            "w": 1,
            "x": 0,
            "y": 0,
            "z": 0
          }
        }
      },
      "required": [
        "position",
        "rotation"
      ],
      "title": "Transform",
      "type": "object"
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
  "properties": {
    "schema_version": {
      "default": 17,
      "title": "Schema Version",
      "type": "integer"
    },
    "greenhouse_id": {
      "title": "Greenhouse Id",
      "type": "string"
    },
    "simulated_day": {
      "title": "Simulated Day",
      "type": "integer"
    },
    "entities": {
      "items": {
        "$ref": "#/$defs/SceneEntity"
      },
      "title": "Entities",
      "type": "array"
    }
  },
  "required": [
    "schema_version",
    "greenhouse_id",
    "simulated_day",
    "entities"
  ],
  "title": "SceneSnapshot",
  "type": "object"
};
