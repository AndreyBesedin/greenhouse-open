// Generated from greenhouse_sim/builder/edit.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const EDIT_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Edit",
  "$defs": {
    "Axis": {
      "enum": [
        "x",
        "y",
        "z"
      ],
      "type": "string"
    },
    "BoxPrimitive": {
      "additionalProperties": false,
      "description": "A box standing on the floor or anything else: its base centred on\n`base`, turned about the vertical by `heading` radians from the\ngreenhouse's x.",
      "properties": {
        "fixture_id": {
          "title": "Fixture Id",
          "type": "string"
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
        "obstructs": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Obstruction"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Obstructs"
        },
        "primitive": {
          "const": "box",
          "default": "box",
          "title": "Primitive",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/FixtureKind",
          "default": "obstacle"
        },
        "base": {
          "$ref": "#/$defs/Vector3"
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
        },
        "heading": {
          "default": 0,
          "title": "Heading",
          "type": "number"
        }
      },
      "required": [
        "fixture_id",
        "base",
        "size_x",
        "size_y",
        "size_z"
      ],
      "title": "BoxPrimitive",
      "type": "object"
    },
    "Camera": {
      "additionalProperties": false,
      "description": "A camera at its position, looking at `target`, with its intrinsics.",
      "properties": {
        "sensor_id": {
          "description": "Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.",
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Sensor Id",
          "type": "string"
        },
        "position": {
          "$ref": "#/$defs/Vector3"
        },
        "cadence_s": {
          "default": 60,
          "minimum": 1,
          "title": "Cadence S",
          "type": "number"
        },
        "kind": {
          "const": "camera",
          "default": "camera",
          "title": "Kind",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/Vector3"
        },
        "intrinsics": {
          "$ref": "#/$defs/CameraIntrinsics"
        }
      },
      "required": [
        "sensor_id",
        "position",
        "target",
        "intrinsics"
      ],
      "title": "Camera",
      "type": "object"
    },
    "CameraIntrinsics": {
      "description": "Pinhole intrinsics of one image stream, in pixels, with the\ncalibration's distortion coefficients exactly as given.",
      "properties": {
        "width": {
          "exclusiveMinimum": 0,
          "title": "Width",
          "type": "integer"
        },
        "height": {
          "exclusiveMinimum": 0,
          "title": "Height",
          "type": "integer"
        },
        "fx": {
          "exclusiveMinimum": 0,
          "title": "Fx",
          "type": "number"
        },
        "fy": {
          "exclusiveMinimum": 0,
          "title": "Fy",
          "type": "number"
        },
        "ppx": {
          "title": "Ppx",
          "type": "number"
        },
        "ppy": {
          "title": "Ppy",
          "type": "number"
        },
        "distortion": {
          "default": [],
          "items": {
            "type": "number"
          },
          "title": "Distortion",
          "type": "array"
        }
      },
      "required": [
        "width",
        "height",
        "fx",
        "fy",
        "ppx",
        "ppy"
      ],
      "title": "CameraIntrinsics",
      "type": "object"
    },
    "Count": {
      "maximum": 500,
      "minimum": 1,
      "type": "integer"
    },
    "CylinderPrimitive": {
      "additionalProperties": false,
      "description": "An upright cylinder, its base centred on `base`.",
      "properties": {
        "fixture_id": {
          "title": "Fixture Id",
          "type": "string"
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
        "obstructs": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Obstruction"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Obstructs"
        },
        "primitive": {
          "const": "cylinder",
          "default": "cylinder",
          "title": "Primitive",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/FixtureKind",
          "default": "obstacle"
        },
        "base": {
          "$ref": "#/$defs/Vector3"
        },
        "radius": {
          "exclusiveMinimum": 0,
          "title": "Radius",
          "type": "number"
        },
        "height": {
          "exclusiveMinimum": 0,
          "title": "Height",
          "type": "number"
        }
      },
      "required": [
        "fixture_id",
        "base",
        "radius",
        "height"
      ],
      "title": "CylinderPrimitive",
      "type": "object"
    },
    "Dehumidifier": {
      "additionalProperties": false,
      "description": "A dehumidifier: the water it takes out of the air at full power, and\nthe heat it gives the air while it does.",
      "properties": {
        "actuator_id": {
          "description": "Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.",
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Actuator Id",
          "type": "string"
        },
        "heading": {
          "default": 0,
          "title": "Heading",
          "type": "number"
        },
        "base": {
          "$ref": "#/$defs/Vector3"
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
        },
        "kind": {
          "const": "dehumidifier",
          "default": "dehumidifier",
          "title": "Kind",
          "type": "string"
        },
        "removal_kg_h": {
          "exclusiveMinimum": 0,
          "title": "Removal Kg H",
          "type": "number"
        },
        "heat_w": {
          "exclusiveMinimum": 0,
          "title": "Heat W",
          "type": "number"
        }
      },
      "required": [
        "actuator_id",
        "base",
        "size_x",
        "size_y",
        "size_z",
        "removal_kg_h",
        "heat_w"
      ],
      "title": "Dehumidifier",
      "type": "object"
    },
    "Equipment": {
      "discriminator": {
        "mapping": {
          "dehumidifier": "#/$defs/Dehumidifier",
          "fan": "#/$defs/Fan",
          "heater": "#/$defs/Heater"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/Fan"
        },
        {
          "$ref": "#/$defs/Heater"
        },
        {
          "$ref": "#/$defs/Dehumidifier"
        }
      ]
    },
    "Fan": {
      "additionalProperties": false,
      "description": "A fan: a rotor of a diameter, centred on `position`, blowing its rated\nflow of air along its heading.",
      "properties": {
        "actuator_id": {
          "description": "Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.",
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Actuator Id",
          "type": "string"
        },
        "heading": {
          "default": 0,
          "title": "Heading",
          "type": "number"
        },
        "kind": {
          "const": "fan",
          "default": "fan",
          "title": "Kind",
          "type": "string"
        },
        "position": {
          "$ref": "#/$defs/Vector3"
        },
        "diameter_m": {
          "exclusiveMinimum": 0,
          "title": "Diameter M",
          "type": "number"
        },
        "flow_m3_s": {
          "exclusiveMinimum": 0,
          "title": "Flow M3 S",
          "type": "number"
        }
      },
      "required": [
        "actuator_id",
        "position",
        "diameter_m",
        "flow_m3_s"
      ],
      "title": "Fan",
      "type": "object"
    },
    "FixtureKind": {
      "description": "What a fixture is, for every consumer of its geometry.",
      "enum": [
        "crop_gutter",
        "bench",
        "slab",
        "walkway",
        "rail",
        "pipe",
        "wire",
        "obstacle"
      ],
      "title": "FixtureKind",
      "type": "string"
    },
    "Heater": {
      "additionalProperties": false,
      "description": "A unit heater: its rated power, all of it given to the air as heat.",
      "properties": {
        "actuator_id": {
          "description": "Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.",
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Actuator Id",
          "type": "string"
        },
        "heading": {
          "default": 0,
          "title": "Heading",
          "type": "number"
        },
        "base": {
          "$ref": "#/$defs/Vector3"
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
        },
        "kind": {
          "const": "heater",
          "default": "heater",
          "title": "Kind",
          "type": "string"
        },
        "power_w": {
          "exclusiveMinimum": 0,
          "title": "Power W",
          "type": "number"
        }
      },
      "required": [
        "actuator_id",
        "base",
        "size_x",
        "size_y",
        "size_z",
        "power_w"
      ],
      "title": "Heater",
      "type": "object"
    },
    "Imperfections": {
      "additionalProperties": false,
      "description": "How a sensor errs, each in its own unit; all nothing for a clean one.\n\nNoise is Gaussian, of a standard deviation; a reading is rounded to the\nquantization step; a fixed bias is added, and a drift that grows linearly\nwith time since the run's start; a sample drops out with a probability;\nand a reading is delivered a fixed time after its sample.",
      "properties": {
        "noise_sd": {
          "default": 0,
          "minimum": 0,
          "title": "Noise Sd",
          "type": "number"
        },
        "quantization": {
          "default": 0,
          "minimum": 0,
          "title": "Quantization",
          "type": "number"
        },
        "bias": {
          "default": 0,
          "title": "Bias",
          "type": "number"
        },
        "drift_per_hour": {
          "default": 0,
          "title": "Drift Per Hour",
          "type": "number"
        },
        "dropout": {
          "default": 0,
          "exclusiveMaximum": 1,
          "minimum": 0,
          "title": "Dropout",
          "type": "number"
        },
        "latency_s": {
          "default": 0,
          "minimum": 0,
          "title": "Latency S",
          "type": "number"
        }
      },
      "title": "Imperfections",
      "type": "object"
    },
    "JsonValue": {},
    "Material": {
      "description": "What a fixture, or a part of the envelope, is made of.",
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
    "Obstruction": {
      "description": "What a fixture stands in the way of.",
      "enum": [
        "movement",
        "airflow",
        "light"
      ],
      "title": "Obstruction",
      "type": "string"
    },
    "Opening": {
      "description": "A door or vent: a rectangle on its host surface, centred at `centre` in\nthe host's own x-y plane, `width` along the host's x and `height` along\nits y, open by `opening`, from 0 (closed) to 1.",
      "properties": {
        "opening_id": {
          "description": "Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.",
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Opening Id",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/OpeningKind"
        },
        "surface_id": {
          "title": "Surface Id",
          "type": "string"
        },
        "centre": {
          "$ref": "#/$defs/Point2"
        },
        "width": {
          "exclusiveMinimum": 0,
          "title": "Width",
          "type": "number"
        },
        "height": {
          "exclusiveMinimum": 0,
          "title": "Height",
          "type": "number"
        },
        "opening": {
          "default": 0,
          "maximum": 1,
          "minimum": 0,
          "title": "Opening",
          "type": "number"
        },
        "largest_angle": {
          "default": 0.7853981633974483,
          "exclusiveMinimum": 0,
          "maximum": 1.5707963267948966,
          "title": "Largest Angle",
          "type": "number"
        }
      },
      "required": [
        "opening_id",
        "kind",
        "surface_id",
        "centre",
        "width",
        "height"
      ],
      "title": "Opening",
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
    "PipePrimitive": {
      "additionalProperties": false,
      "description": "A straight pipe, its axis from `start` to `end`.",
      "properties": {
        "fixture_id": {
          "title": "Fixture Id",
          "type": "string"
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
        "obstructs": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Obstruction"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Obstructs"
        },
        "primitive": {
          "const": "pipe",
          "default": "pipe",
          "title": "Primitive",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/FixtureKind",
          "default": "pipe"
        },
        "start": {
          "$ref": "#/$defs/Vector3"
        },
        "end": {
          "$ref": "#/$defs/Vector3"
        },
        "radius": {
          "exclusiveMinimum": 0,
          "title": "Radius",
          "type": "number"
        }
      },
      "required": [
        "fixture_id",
        "start",
        "end",
        "radius"
      ],
      "title": "PipePrimitive",
      "type": "object"
    },
    "PipeRunPrimitive": {
      "additionalProperties": false,
      "description": "Pipes repeated in parallel, such as heating pipes stacked along a wall:\nthe first from `start` to `end`, each next one `step` further on, `count`\nin all. Each is its own multiple of the step from the first, and is called\n`<fixture_id>_<n>`, from 1.",
      "properties": {
        "fixture_id": {
          "title": "Fixture Id",
          "type": "string"
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
        "obstructs": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Obstruction"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Obstructs"
        },
        "primitive": {
          "const": "pipe_run",
          "default": "pipe_run",
          "title": "Primitive",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/FixtureKind",
          "default": "pipe"
        },
        "start": {
          "$ref": "#/$defs/Vector3"
        },
        "end": {
          "$ref": "#/$defs/Vector3"
        },
        "radius": {
          "exclusiveMinimum": 0,
          "title": "Radius",
          "type": "number"
        },
        "count": {
          "exclusiveMinimum": 0,
          "maximum": 1000,
          "title": "Count",
          "type": "integer"
        },
        "step": {
          "$ref": "#/$defs/Vector3"
        }
      },
      "required": [
        "fixture_id",
        "start",
        "end",
        "radius",
        "count",
        "step"
      ],
      "title": "PipeRunPrimitive",
      "type": "object"
    },
    "PlaceItems": {
      "additionalProperties": false,
      "description": "Pieces of equipment, sensors, zones or fixtures like `item`, the\nfirst where it stands and each next `step` further, named after its\nidentifier.",
      "properties": {
        "edit": {
          "const": "place_items",
          "default": "place_items",
          "title": "Edit",
          "type": "string"
        },
        "item": {
          "anyOf": [
            {
              "$ref": "#/$defs/Equipment"
            },
            {
              "$ref": "#/$defs/Sensor"
            },
            {
              "$ref": "#/$defs/Zone"
            },
            {
              "$ref": "#/$defs/Primitive"
            }
          ],
          "title": "Item"
        },
        "count": {
          "$ref": "#/$defs/Count",
          "default": 1
        },
        "step": {
          "anyOf": [
            {
              "$ref": "#/$defs/Vector3"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "item"
      ],
      "title": "PlaceItems",
      "type": "object"
    },
    "PlaceOpenings": {
      "additionalProperties": false,
      "description": "On each chosen surface, doors or vents like `opening`, the first at\nits centre and each next `step` further in the surface's plane.",
      "properties": {
        "edit": {
          "const": "place_openings",
          "default": "place_openings",
          "title": "Edit",
          "type": "string"
        },
        "opening": {
          "$ref": "#/$defs/Opening"
        },
        "surfaces": {
          "items": {
            "type": "string"
          },
          "title": "Surfaces",
          "type": "array"
        },
        "count": {
          "$ref": "#/$defs/Count",
          "default": 1
        },
        "step": {
          "anyOf": [
            {
              "$ref": "#/$defs/Point2"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "opening",
        "surfaces"
      ],
      "title": "PlaceOpenings",
      "type": "object"
    },
    "Point2": {
      "description": "A point in a shape's own x-y plane.",
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
    "PointKind": {
      "enum": [
        "temperature",
        "humidity",
        "co2",
        "air_speed",
        "par",
        "outside_temperature",
        "outside_humidity",
        "wind_speed",
        "wind_direction",
        "barometric_pressure"
      ],
      "type": "string"
    },
    "PointSensor": {
      "additionalProperties": false,
      "description": "A sensor reading one quantity of the air at its position, or, outside\nthe house, of the weather.",
      "properties": {
        "sensor_id": {
          "description": "Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.",
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Sensor Id",
          "type": "string"
        },
        "position": {
          "$ref": "#/$defs/Vector3"
        },
        "cadence_s": {
          "default": 60,
          "minimum": 1,
          "title": "Cadence S",
          "type": "number"
        },
        "kind": {
          "$ref": "#/$defs/PointKind"
        },
        "imperfections": {
          "$ref": "#/$defs/Imperfections",
          "default": {
            "noise_sd": 0,
            "quantization": 0,
            "bias": 0,
            "drift_per_hour": 0,
            "dropout": 0,
            "latency_s": 0
          }
        }
      },
      "required": [
        "sensor_id",
        "position",
        "kind"
      ],
      "title": "PointSensor",
      "type": "object"
    },
    "Primitive": {
      "discriminator": {
        "mapping": {
          "box": "#/$defs/BoxPrimitive",
          "cylinder": "#/$defs/CylinderPrimitive",
          "pipe": "#/$defs/PipePrimitive",
          "pipe_run": "#/$defs/PipeRunPrimitive",
          "rail": "#/$defs/RailPrimitive",
          "tray": "#/$defs/TrayPrimitive",
          "walkway": "#/$defs/WalkwayPrimitive"
        },
        "propertyName": "primitive"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/BoxPrimitive"
        },
        {
          "$ref": "#/$defs/CylinderPrimitive"
        },
        {
          "$ref": "#/$defs/PipePrimitive"
        },
        {
          "$ref": "#/$defs/PipeRunPrimitive"
        },
        {
          "$ref": "#/$defs/RailPrimitive"
        },
        {
          "$ref": "#/$defs/TrayPrimitive"
        },
        {
          "$ref": "#/$defs/WalkwayPrimitive"
        }
      ]
    },
    "RailPrimitive": {
      "additionalProperties": false,
      "description": "A rail of two parallel tubes, `gauge` apart from axis to axis, either\nside of its centre line from `start` to `end`. Its tubes are\n`<fixture_id>_right` and `<fixture_id>_left`, as seen looking along it.",
      "properties": {
        "fixture_id": {
          "title": "Fixture Id",
          "type": "string"
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
        "obstructs": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Obstruction"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Obstructs"
        },
        "primitive": {
          "const": "rail",
          "default": "rail",
          "title": "Primitive",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/FixtureKind",
          "default": "rail"
        },
        "start": {
          "$ref": "#/$defs/Vector3"
        },
        "end": {
          "$ref": "#/$defs/Vector3"
        },
        "gauge": {
          "exclusiveMinimum": 0,
          "title": "Gauge",
          "type": "number"
        },
        "tube_radius": {
          "exclusiveMinimum": 0,
          "title": "Tube Radius",
          "type": "number"
        }
      },
      "required": [
        "fixture_id",
        "start",
        "end",
        "gauge",
        "tube_radius"
      ],
      "title": "RailPrimitive",
      "type": "object"
    },
    "RemoveItems": {
      "additionalProperties": false,
      "description": "The chosen equipment, sensors, zones, fixtures, doors and vents\ntaken out.",
      "properties": {
        "edit": {
          "const": "remove_items",
          "default": "remove_items",
          "title": "Edit",
          "type": "string"
        },
        "items": {
          "items": {
            "type": "string"
          },
          "title": "Items",
          "type": "array"
        }
      },
      "required": [
        "items"
      ],
      "title": "RemoveItems",
      "type": "object"
    },
    "RepeatItems": {
      "additionalProperties": false,
      "description": "Each chosen piece of equipment, sensor, zone or fixture copied\n`count` times, each copy `step` further than the one before.",
      "properties": {
        "edit": {
          "const": "repeat_items",
          "default": "repeat_items",
          "title": "Edit",
          "type": "string"
        },
        "items": {
          "items": {
            "type": "string"
          },
          "title": "Items",
          "type": "array"
        },
        "count": {
          "$ref": "#/$defs/Count"
        },
        "step": {
          "$ref": "#/$defs/Vector3"
        }
      },
      "required": [
        "items",
        "count",
        "step"
      ],
      "title": "RepeatItems",
      "type": "object"
    },
    "RepeatOpenings": {
      "additionalProperties": false,
      "description": "Each chosen door or vent copied `count` times on its surface, each\ncopy `step` further than the one before.",
      "properties": {
        "edit": {
          "const": "repeat_openings",
          "default": "repeat_openings",
          "title": "Edit",
          "type": "string"
        },
        "openings": {
          "items": {
            "type": "string"
          },
          "title": "Openings",
          "type": "array"
        },
        "count": {
          "$ref": "#/$defs/Count"
        },
        "step": {
          "$ref": "#/$defs/Point2"
        }
      },
      "required": [
        "openings",
        "count",
        "step"
      ],
      "title": "RepeatOpenings",
      "type": "object"
    },
    "Sensor": {
      "discriminator": {
        "mapping": {
          "air_speed": "#/$defs/PointSensor",
          "barometric_pressure": "#/$defs/PointSensor",
          "camera": "#/$defs/Camera",
          "co2": "#/$defs/PointSensor",
          "humidity": "#/$defs/PointSensor",
          "outside_humidity": "#/$defs/PointSensor",
          "outside_temperature": "#/$defs/PointSensor",
          "par": "#/$defs/PointSensor",
          "temperature": "#/$defs/PointSensor",
          "wind_direction": "#/$defs/PointSensor",
          "wind_speed": "#/$defs/PointSensor"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/PointSensor"
        },
        {
          "$ref": "#/$defs/Camera"
        }
      ]
    },
    "SetField": {
      "additionalProperties": false,
      "description": "One field, a nested one by its path (`base.z`), given one value over\nthe chosen items: equipment, sensors, zones, fixtures, doors or\nvents.",
      "properties": {
        "edit": {
          "const": "set_field",
          "default": "set_field",
          "title": "Edit",
          "type": "string"
        },
        "items": {
          "items": {
            "type": "string"
          },
          "title": "Items",
          "type": "array"
        },
        "path": {
          "minLength": 1,
          "title": "Path",
          "type": "string"
        },
        "value": {
          "$ref": "#/$defs/JsonValue"
        }
      },
      "required": [
        "items",
        "path",
        "value"
      ],
      "title": "SetField",
      "type": "object"
    },
    "SetValue": {
      "additionalProperties": false,
      "description": "One field of the installation, by its path from the top\n(`envelope.length`), given a value.",
      "properties": {
        "edit": {
          "const": "set_value",
          "default": "set_value",
          "title": "Edit",
          "type": "string"
        },
        "path": {
          "minLength": 1,
          "title": "Path",
          "type": "string"
        },
        "value": {
          "$ref": "#/$defs/JsonValue"
        }
      },
      "required": [
        "path",
        "value"
      ],
      "title": "SetValue",
      "type": "object"
    },
    "SpaceItems": {
      "additionalProperties": false,
      "description": "The chosen pieces of equipment, sensors, zones and fixtures spaced\nevenly along an axis of the greenhouse.",
      "properties": {
        "edit": {
          "const": "space_items",
          "default": "space_items",
          "title": "Edit",
          "type": "string"
        },
        "items": {
          "items": {
            "type": "string"
          },
          "title": "Items",
          "type": "array"
        },
        "axis": {
          "$ref": "#/$defs/Axis"
        }
      },
      "required": [
        "items",
        "axis"
      ],
      "title": "SpaceItems",
      "type": "object"
    },
    "SpaceOpenings": {
      "additionalProperties": false,
      "description": "The chosen doors and vents of one surface spaced evenly along it.",
      "properties": {
        "edit": {
          "const": "space_openings",
          "default": "space_openings",
          "title": "Edit",
          "type": "string"
        },
        "openings": {
          "items": {
            "type": "string"
          },
          "title": "Openings",
          "type": "array"
        }
      },
      "required": [
        "openings"
      ],
      "title": "SpaceOpenings",
      "type": "object"
    },
    "SpreadOpenings": {
      "additionalProperties": false,
      "description": "On each chosen surface, `count` doors or vents like `opening`, spread\nevenly along it.",
      "properties": {
        "edit": {
          "const": "spread_openings",
          "default": "spread_openings",
          "title": "Edit",
          "type": "string"
        },
        "opening": {
          "$ref": "#/$defs/Opening"
        },
        "surfaces": {
          "items": {
            "type": "string"
          },
          "title": "Surfaces",
          "type": "array"
        },
        "count": {
          "$ref": "#/$defs/Count"
        }
      },
      "required": [
        "opening",
        "surfaces",
        "count"
      ],
      "title": "SpreadOpenings",
      "type": "object"
    },
    "Strip": {
      "additionalProperties": false,
      "description": "A rectangle of the floor: a centre line from `start` to `end`, `width`\nwide.",
      "properties": {
        "start": {
          "$ref": "#/$defs/Point2"
        },
        "end": {
          "$ref": "#/$defs/Point2"
        },
        "width": {
          "exclusiveMinimum": 0,
          "title": "Width",
          "type": "number"
        }
      },
      "required": [
        "start",
        "end",
        "width"
      ],
      "title": "Strip",
      "type": "object"
    },
    "TrayPrimitive": {
      "additionalProperties": false,
      "description": "An open tray, such as a crop gutter: `width` across and `depth` deep,\nits bottom's centre line from `start` to `end`. It may slope, as gutters\ndo to drain; it stays level across.",
      "properties": {
        "fixture_id": {
          "title": "Fixture Id",
          "type": "string"
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
        "obstructs": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Obstruction"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Obstructs"
        },
        "primitive": {
          "const": "tray",
          "default": "tray",
          "title": "Primitive",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/FixtureKind",
          "default": "crop_gutter"
        },
        "start": {
          "$ref": "#/$defs/Vector3"
        },
        "end": {
          "$ref": "#/$defs/Vector3"
        },
        "width": {
          "exclusiveMinimum": 0,
          "title": "Width",
          "type": "number"
        },
        "depth": {
          "exclusiveMinimum": 0,
          "title": "Depth",
          "type": "number"
        }
      },
      "required": [
        "fixture_id",
        "start",
        "end",
        "width",
        "depth"
      ],
      "title": "TrayPrimitive",
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
    },
    "WalkwayPrimitive": {
      "additionalProperties": false,
      "description": "A path on the floor, `width` wide, its centre line from `start` to\n`end`.",
      "properties": {
        "fixture_id": {
          "title": "Fixture Id",
          "type": "string"
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
        "obstructs": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Obstruction"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Obstructs"
        },
        "primitive": {
          "const": "walkway",
          "default": "walkway",
          "title": "Primitive",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/FixtureKind",
          "default": "walkway"
        },
        "start": {
          "$ref": "#/$defs/Point2"
        },
        "end": {
          "$ref": "#/$defs/Point2"
        },
        "width": {
          "exclusiveMinimum": 0,
          "title": "Width",
          "type": "number"
        }
      },
      "required": [
        "fixture_id",
        "start",
        "end",
        "width"
      ],
      "title": "WalkwayPrimitive",
      "type": "object"
    },
    "Zone": {
      "additionalProperties": false,
      "description": "A service zone or keep-out volume: a strip of the floor, rising\n`height` above it.",
      "properties": {
        "zone_id": {
          "title": "Zone Id",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/ZoneKind"
        },
        "area": {
          "$ref": "#/$defs/Strip"
        },
        "height": {
          "exclusiveMinimum": 0,
          "title": "Height",
          "type": "number"
        }
      },
      "required": [
        "zone_id",
        "kind",
        "area",
        "height"
      ],
      "title": "Zone",
      "type": "object"
    },
    "ZoneKind": {
      "description": "What an area of the floor is kept for.",
      "enum": [
        "service",
        "keep_out"
      ],
      "title": "ZoneKind",
      "type": "string"
    }
  },
  "discriminator": {
    "mapping": {
      "place_items": "#/$defs/PlaceItems",
      "place_openings": "#/$defs/PlaceOpenings",
      "remove_items": "#/$defs/RemoveItems",
      "repeat_items": "#/$defs/RepeatItems",
      "repeat_openings": "#/$defs/RepeatOpenings",
      "set_field": "#/$defs/SetField",
      "set_value": "#/$defs/SetValue",
      "space_items": "#/$defs/SpaceItems",
      "space_openings": "#/$defs/SpaceOpenings",
      "spread_openings": "#/$defs/SpreadOpenings"
    },
    "propertyName": "edit"
  },
  "oneOf": [
    {
      "$ref": "#/$defs/PlaceItems"
    },
    {
      "$ref": "#/$defs/RepeatItems"
    },
    {
      "$ref": "#/$defs/SpaceItems"
    },
    {
      "$ref": "#/$defs/PlaceOpenings"
    },
    {
      "$ref": "#/$defs/SpreadOpenings"
    },
    {
      "$ref": "#/$defs/RepeatOpenings"
    },
    {
      "$ref": "#/$defs/SpaceOpenings"
    },
    {
      "$ref": "#/$defs/SetField"
    },
    {
      "$ref": "#/$defs/SetValue"
    },
    {
      "$ref": "#/$defs/RemoveItems"
    }
  ]
};
