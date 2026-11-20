// Generated from greenhouse_sim/services/builder.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const ASSESSED_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "Boundaries": {
      "additionalProperties": {
        "$ref": "#/$defs/WallBoundary"
      },
      "minProperties": 1,
      "propertyNames": {
        "$ref": "#/$defs/WallId"
      },
      "type": "object"
    },
    "BoxPrimitive": {
      "additionalProperties": false,
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
        "material",
        "obstructs",
        "primitive",
        "kind",
        "base",
        "size_x",
        "size_y",
        "size_z",
        "heading"
      ],
      "title": "BoxPrimitive",
      "type": "object"
    },
    "Camera": {
      "additionalProperties": false,
      "properties": {
        "sensor_id": {
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
        "cadence_s",
        "kind",
        "target",
        "intrinsics"
      ],
      "title": "Camera",
      "type": "object"
    },
    "CameraIntrinsics": {
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
        "ppy",
        "distortion"
      ],
      "title": "CameraIntrinsics",
      "type": "object"
    },
    "Cover": {
      "additionalProperties": false,
      "properties": {
        "roof": {
          "$ref": "#/$defs/CoverChoice"
        },
        "walls": {
          "additionalProperties": {
            "$ref": "#/$defs/CoverChoice"
          },
          "default": {},
          "propertyNames": {
            "$ref": "#/$defs/WallId"
          },
          "title": "Walls",
          "type": "object"
        }
      },
      "required": [
        "roof",
        "walls"
      ],
      "title": "Cover",
      "type": "object"
    },
    "CoverChoice": {
      "anyOf": [
        {
          "$ref": "#/$defs/CoverMaterialName"
        },
        {
          "$ref": "#/$defs/CoverMaterial"
        }
      ]
    },
    "CoverMaterial": {
      "additionalProperties": false,
      "properties": {
        "shortwave_beam_transmittance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Shortwave Beam Transmittance",
          "type": "number"
        },
        "shortwave_diffuse_transmittance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Shortwave Diffuse Transmittance",
          "type": "number"
        },
        "shortwave_reflectance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Shortwave Reflectance",
          "type": "number"
        },
        "longwave_emissivity": {
          "maximum": 1,
          "minimum": 0,
          "title": "Longwave Emissivity",
          "type": "number"
        },
        "longwave_transmittance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Longwave Transmittance",
          "type": "number"
        },
        "thickness_m": {
          "exclusiveMinimum": 0,
          "title": "Thickness M",
          "type": "number"
        },
        "conductivity_w_m_k": {
          "exclusiveMinimum": 0,
          "title": "Conductivity W M K",
          "type": "number"
        },
        "volumetric_heat_capacity_j_m3_k": {
          "exclusiveMinimum": 0,
          "maximum": 4180000,
          "title": "Volumetric Heat Capacity J M3 K",
          "type": "number"
        }
      },
      "required": [
        "shortwave_beam_transmittance",
        "shortwave_diffuse_transmittance",
        "shortwave_reflectance",
        "longwave_emissivity",
        "longwave_transmittance",
        "thickness_m",
        "conductivity_w_m_k",
        "volumetric_heat_capacity_j_m3_k"
      ],
      "title": "CoverMaterial",
      "type": "object"
    },
    "CoverMaterialName": {
      "enum": [
        "single_glass"
      ],
      "title": "CoverMaterialName",
      "type": "string"
    },
    "CropModel": {
      "enum": [
        "simple",
        "organ",
        "reduced_tomgro",
        "vanthoor_katzin"
      ],
      "title": "CropModel",
      "type": "string"
    },
    "CropRows": {
      "additionalProperties": false,
      "properties": {
        "origin": {
          "$ref": "#/$defs/Point2"
        },
        "heading": {
          "default": 0,
          "title": "Heading",
          "type": "number"
        },
        "rows": {
          "exclusiveMinimum": 0,
          "maximum": 1000,
          "title": "Rows",
          "type": "integer"
        },
        "positions_per_row": {
          "exclusiveMinimum": 0,
          "maximum": 10000,
          "title": "Positions Per Row",
          "type": "integer"
        },
        "plant_pitch": {
          "exclusiveMinimum": 0,
          "title": "Plant Pitch",
          "type": "number"
        },
        "row_spacing": {
          "exclusiveMinimum": 0,
          "title": "Row Spacing",
          "type": "number"
        },
        "pair_gap": {
          "anyOf": [
            {
              "exclusiveMinimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Pair Gap"
        },
        "support": {
          "anyOf": [
            {
              "$ref": "#/$defs/RowSupport"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "rails": {
          "anyOf": [
            {
              "$ref": "#/$defs/RowRails"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "wires": {
          "anyOf": [
            {
              "$ref": "#/$defs/CropWires"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "origin",
        "heading",
        "rows",
        "positions_per_row",
        "plant_pitch",
        "row_spacing",
        "pair_gap",
        "support",
        "rails",
        "wires"
      ],
      "title": "CropRows",
      "type": "object"
    },
    "CropWires": {
      "additionalProperties": false,
      "properties": {
        "height": {
          "exclusiveMinimum": 0,
          "title": "Height",
          "type": "number"
        },
        "radius": {
          "default": 0.0025,
          "exclusiveMinimum": 0,
          "title": "Radius",
          "type": "number"
        },
        "offset": {
          "default": 0,
          "minimum": 0,
          "title": "Offset",
          "type": "number"
        }
      },
      "required": [
        "height",
        "radius",
        "offset"
      ],
      "title": "CropWires",
      "type": "object"
    },
    "CylinderPrimitive": {
      "additionalProperties": false,
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
        "material",
        "obstructs",
        "primitive",
        "kind",
        "base",
        "radius",
        "height"
      ],
      "title": "CylinderPrimitive",
      "type": "object"
    },
    "Dehumidifier": {
      "additionalProperties": false,
      "properties": {
        "actuator_id": {
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
        "heading",
        "base",
        "size_x",
        "size_y",
        "size_z",
        "kind",
        "removal_kg_h",
        "heat_w"
      ],
      "title": "Dehumidifier",
      "type": "object"
    },
    "DraftRevision": {
      "properties": {
        "draft_id": {
          "title": "Draft Id",
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
        "revision",
        "saved_at"
      ],
      "title": "DraftRevision",
      "type": "object"
    },
    "Envelope": {
      "properties": {
        "length": {
          "exclusiveMinimum": 0,
          "maximum": 500,
          "title": "Length",
          "type": "number"
        },
        "width": {
          "exclusiveMinimum": 0,
          "maximum": 500,
          "title": "Width",
          "type": "number"
        },
        "eave_height": {
          "exclusiveMinimum": 0,
          "maximum": 50,
          "title": "Eave Height",
          "type": "number"
        },
        "ridge_height": {
          "exclusiveMinimum": 0,
          "maximum": 50,
          "title": "Ridge Height",
          "type": "number"
        },
        "spans": {
          "default": 1,
          "exclusiveMinimum": 0,
          "maximum": 100,
          "title": "Spans",
          "type": "integer"
        },
        "bays": {
          "default": 1,
          "exclusiveMinimum": 0,
          "maximum": 200,
          "title": "Bays",
          "type": "integer"
        },
        "inner_posts": {
          "anyOf": [
            {
              "items": {
                "type": "integer"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Inner Posts"
        },
        "openings": {
          "default": [],
          "items": {
            "$ref": "#/$defs/Opening"
          },
          "title": "Openings",
          "type": "array"
        },
        "origin": {
          "$ref": "#/$defs/Transform",
          "default": {
            "position": {
              "x": 0,
              "y": 0,
              "z": 0
            },
            "rotation": {
              "w": 1,
              "x": 0,
              "y": 0,
              "z": 0
            }
          }
        }
      },
      "required": [
        "length",
        "width",
        "eave_height",
        "ridge_height",
        "spans",
        "bays",
        "openings",
        "origin"
      ],
      "title": "Envelope",
      "type": "object"
    },
    "Equipment": {
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
      "properties": {
        "actuator_id": {
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
        "heading",
        "kind",
        "position",
        "diameter_m",
        "flow_m3_s"
      ],
      "title": "Fan",
      "type": "object"
    },
    "Finding": {
      "additionalProperties": false,
      "properties": {
        "severity": {
          "enum": [
            "error",
            "warning"
          ],
          "title": "Severity",
          "type": "string"
        },
        "code": {
          "title": "Code",
          "type": "string"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "items": {
          "default": [],
          "items": {
            "type": "string"
          },
          "title": "Items",
          "type": "array"
        },
        "rows": {
          "default": [],
          "items": {
            "type": "integer"
          },
          "title": "Rows",
          "type": "array"
        }
      },
      "required": [
        "severity",
        "code",
        "message",
        "items",
        "rows"
      ],
      "title": "Finding",
      "type": "object"
    },
    "FixtureKind": {
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
    "Floor": {
      "additionalProperties": false,
      "properties": {
        "surface": {
          "$ref": "#/$defs/FloorSurface"
        },
        "layers": {
          "items": {
            "$ref": "#/$defs/FloorLayer"
          },
          "minItems": 1,
          "title": "Layers",
          "type": "array"
        },
        "deep_soil_temperature_c": {
          "$ref": "#/$defs/Temperature"
        }
      },
      "required": [
        "surface",
        "layers",
        "deep_soil_temperature_c"
      ],
      "title": "Floor",
      "type": "object"
    },
    "FloorLayer": {
      "additionalProperties": false,
      "properties": {
        "thickness_m": {
          "exclusiveMinimum": 0,
          "title": "Thickness M",
          "type": "number"
        },
        "material": {
          "$ref": "#/$defs/LayerChoice"
        }
      },
      "required": [
        "thickness_m",
        "material"
      ],
      "title": "FloorLayer",
      "type": "object"
    },
    "FloorSurface": {
      "additionalProperties": false,
      "properties": {
        "shortwave_reflectance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Shortwave Reflectance",
          "type": "number"
        },
        "longwave_emissivity": {
          "maximum": 1,
          "minimum": 0,
          "title": "Longwave Emissivity",
          "type": "number"
        }
      },
      "required": [
        "shortwave_reflectance",
        "longwave_emissivity"
      ],
      "title": "FloorSurface",
      "type": "object"
    },
    "Heater": {
      "additionalProperties": false,
      "properties": {
        "actuator_id": {
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
        "heading",
        "base",
        "size_x",
        "size_y",
        "size_z",
        "kind",
        "power_w"
      ],
      "title": "Heater",
      "type": "object"
    },
    "HouseComponents": {
      "additionalProperties": false,
      "properties": {
        "cover": {
          "anyOf": [
            {
              "$ref": "#/$defs/Cover"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "boundaries": {
          "anyOf": [
            {
              "$ref": "#/$defs/Boundaries"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "floor": {
          "anyOf": [
            {
              "$ref": "#/$defs/Floor"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "screens": {
          "anyOf": [
            {
              "$ref": "#/$defs/Screens"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pipe_networks": {
          "anyOf": [
            {
              "$ref": "#/$defs/PipeNetworks"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "title": "HouseComponents",
      "type": "object"
    },
    "Imperfections": {
      "additionalProperties": false,
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
      "required": [
        "noise_sd",
        "quantization",
        "bias",
        "drift_per_hour",
        "dropout",
        "latency_s"
      ],
      "title": "Imperfections",
      "type": "object"
    },
    "Installation": {
      "additionalProperties": false,
      "properties": {
        "installation_id": {
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Installation Id",
          "type": "string"
        },
        "name": {
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "envelope": {
          "$ref": "#/$defs/Envelope"
        },
        "layout": {
          "$ref": "#/$defs/Layout"
        },
        "row_crops": {
          "default": [],
          "items": {
            "$ref": "#/$defs/RowCrop"
          },
          "title": "Row Crops",
          "type": "array"
        },
        "components": {
          "anyOf": [
            {
              "$ref": "#/$defs/HouseComponents"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "installation_id",
        "name",
        "envelope",
        "layout",
        "row_crops"
      ],
      "title": "Installation",
      "type": "object"
    },
    "LayerChoice": {
      "anyOf": [
        {
          "$ref": "#/$defs/LayerMaterialName"
        },
        {
          "$ref": "#/$defs/LayerMaterial"
        }
      ]
    },
    "LayerMaterial": {
      "additionalProperties": false,
      "properties": {
        "conductivity_w_m_k": {
          "exclusiveMinimum": 0,
          "title": "Conductivity W M K",
          "type": "number"
        },
        "volumetric_heat_capacity_j_m3_k": {
          "exclusiveMinimum": 0,
          "maximum": 4180000,
          "title": "Volumetric Heat Capacity J M3 K",
          "type": "number"
        }
      },
      "required": [
        "conductivity_w_m_k",
        "volumetric_heat_capacity_j_m3_k"
      ],
      "title": "LayerMaterial",
      "type": "object"
    },
    "LayerMaterialName": {
      "enum": [
        "concrete",
        "soil"
      ],
      "title": "LayerMaterialName",
      "type": "string"
    },
    "Layout": {
      "additionalProperties": false,
      "properties": {
        "crop_rows": {
          "anyOf": [
            {
              "$ref": "#/$defs/CropRows"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "placed": {
          "default": [],
          "items": {
            "$ref": "#/$defs/Primitive"
          },
          "title": "Placed",
          "type": "array"
        },
        "zones": {
          "default": [],
          "items": {
            "$ref": "#/$defs/Zone"
          },
          "title": "Zones",
          "type": "array"
        },
        "equipment": {
          "default": [],
          "items": {
            "$ref": "#/$defs/Equipment"
          },
          "title": "Equipment",
          "type": "array"
        },
        "sensors": {
          "default": [],
          "items": {
            "$ref": "#/$defs/Sensor"
          },
          "title": "Sensors",
          "type": "array"
        }
      },
      "required": [
        "crop_rows",
        "placed",
        "zones",
        "equipment",
        "sensors"
      ],
      "title": "Layout",
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
    "Obstruction": {
      "enum": [
        "movement",
        "airflow",
        "light"
      ],
      "title": "Obstruction",
      "type": "string"
    },
    "OnASpace": {
      "additionalProperties": false,
      "properties": {
        "faces": {
          "const": "space",
          "default": "space",
          "title": "Faces",
          "type": "string"
        },
        "kind": {
          "enum": [
            "corridor",
            "headhouse",
            "house"
          ],
          "title": "Kind",
          "type": "string"
        },
        "temperature_c": {
          "anyOf": [
            {
              "$ref": "#/$defs/Temperature"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "recording": {
          "anyOf": [
            {
              "pattern": "^[a-z0-9][a-z0-9_.-]{0,95}\\.csv$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recording"
        }
      },
      "required": [
        "faces",
        "kind"
      ],
      "title": "OnASpace",
      "type": "object"
    },
    "OnNothing": {
      "additionalProperties": false,
      "properties": {
        "faces": {
          "const": "nothing",
          "default": "nothing",
          "title": "Faces",
          "type": "string"
        }
      },
      "required": [
        "faces"
      ],
      "title": "OnNothing",
      "type": "object"
    },
    "OnTheOutside": {
      "additionalProperties": false,
      "properties": {
        "faces": {
          "const": "outside",
          "default": "outside",
          "title": "Faces",
          "type": "string"
        }
      },
      "required": [
        "faces"
      ],
      "title": "OnTheOutside",
      "type": "object"
    },
    "Opening": {
      "properties": {
        "opening_id": {
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
        "height",
        "opening",
        "largest_angle"
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
    "PipeKind": {
      "enum": [
        "rail",
        "grow",
        "perimeter"
      ],
      "title": "PipeKind",
      "type": "string"
    },
    "PipeNetwork": {
      "additionalProperties": false,
      "properties": {
        "network_id": {
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Network Id",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/PipeKind"
        },
        "length_m": {
          "exclusiveMinimum": 0,
          "title": "Length M",
          "type": "number"
        },
        "outer_diameter_m": {
          "exclusiveMinimum": 0,
          "title": "Outer Diameter M",
          "type": "number"
        },
        "inner_diameter_m": {
          "exclusiveMinimum": 0,
          "title": "Inner Diameter M",
          "type": "number"
        },
        "height_m": {
          "minimum": 0,
          "title": "Height M",
          "type": "number"
        },
        "longwave_emissivity": {
          "maximum": 1,
          "minimum": 0,
          "title": "Longwave Emissivity",
          "type": "number"
        }
      },
      "required": [
        "network_id",
        "kind",
        "length_m",
        "outer_diameter_m",
        "inner_diameter_m",
        "height_m",
        "longwave_emissivity"
      ],
      "title": "PipeNetwork",
      "type": "object"
    },
    "PipeNetworks": {
      "items": {
        "$ref": "#/$defs/PipeNetwork"
      },
      "minItems": 1,
      "type": "array"
    },
    "PipePrimitive": {
      "additionalProperties": false,
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
        "material",
        "obstructs",
        "primitive",
        "kind",
        "start",
        "end",
        "radius"
      ],
      "title": "PipePrimitive",
      "type": "object"
    },
    "PipeRunPrimitive": {
      "additionalProperties": false,
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
        "material",
        "obstructs",
        "primitive",
        "kind",
        "start",
        "end",
        "radius",
        "count",
        "step"
      ],
      "title": "PipeRunPrimitive",
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
        "barometric_pressure",
        "downward_longwave",
        "sky_temperature",
        "diffuse_radiation"
      ],
      "type": "string"
    },
    "PointSensor": {
      "additionalProperties": false,
      "properties": {
        "sensor_id": {
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
        "cadence_s",
        "kind",
        "imperfections"
      ],
      "title": "PointSensor",
      "type": "object"
    },
    "Primitive": {
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
    "RailPrimitive": {
      "additionalProperties": false,
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
        "material",
        "obstructs",
        "primitive",
        "kind",
        "start",
        "end",
        "gauge",
        "tube_radius"
      ],
      "title": "RailPrimitive",
      "type": "object"
    },
    "RowCrop": {
      "additionalProperties": false,
      "properties": {
        "row": {
          "exclusiveMinimum": 0,
          "title": "Row",
          "type": "integer"
        },
        "crop_model": {
          "$ref": "#/$defs/CropModel"
        },
        "variety": {
          "minLength": 1,
          "title": "Variety",
          "type": "string"
        }
      },
      "required": [
        "row",
        "crop_model",
        "variety"
      ],
      "title": "RowCrop",
      "type": "object"
    },
    "RowRails": {
      "additionalProperties": false,
      "properties": {
        "gauge": {
          "exclusiveMinimum": 0,
          "title": "Gauge",
          "type": "number"
        },
        "tube_radius": {
          "exclusiveMinimum": 0,
          "title": "Tube Radius",
          "type": "number"
        },
        "height": {
          "exclusiveMinimum": 0,
          "title": "Height",
          "type": "number"
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
        }
      },
      "required": [
        "gauge",
        "tube_radius",
        "height",
        "material"
      ],
      "title": "RowRails",
      "type": "object"
    },
    "RowSupport": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "default": "crop_gutter",
          "enum": [
            "crop_gutter",
            "bench"
          ],
          "title": "Kind",
          "type": "string"
        },
        "height": {
          "exclusiveMinimum": 0,
          "title": "Height",
          "type": "number"
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
        },
        "overhang": {
          "default": 0.25,
          "minimum": 0,
          "title": "Overhang",
          "type": "number"
        },
        "offset": {
          "default": 0,
          "title": "Offset",
          "type": "number"
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
        "leg_spacing": {
          "anyOf": [
            {
              "exclusiveMinimum": 0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Leg Spacing"
        },
        "leg_radius": {
          "default": 0.02,
          "exclusiveMinimum": 0,
          "title": "Leg Radius",
          "type": "number"
        },
        "slab": {
          "anyOf": [
            {
              "$ref": "#/$defs/Slab"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "kind",
        "height",
        "width",
        "depth",
        "overhang",
        "offset",
        "material",
        "leg_spacing",
        "leg_radius",
        "slab"
      ],
      "title": "RowSupport",
      "type": "object"
    },
    "Screen": {
      "additionalProperties": false,
      "properties": {
        "screen_id": {
          "pattern": "^[A-Za-z0-9_.-]+$",
          "title": "Screen Id",
          "type": "string"
        },
        "kind": {
          "$ref": "#/$defs/ScreenKind"
        },
        "material": {
          "$ref": "#/$defs/ScreenChoice"
        },
        "height_m": {
          "exclusiveMinimum": 0,
          "title": "Height M",
          "type": "number"
        },
        "extent": {
          "anyOf": [
            {
              "$ref": "#/$defs/Strip"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "closure": {
          "default": 0,
          "maximum": 1,
          "minimum": 0,
          "title": "Closure",
          "type": "number"
        }
      },
      "required": [
        "screen_id",
        "kind",
        "material",
        "height_m",
        "closure"
      ],
      "title": "Screen",
      "type": "object"
    },
    "ScreenChoice": {
      "anyOf": [
        {
          "$ref": "#/$defs/ScreenClothName"
        },
        {
          "$ref": "#/$defs/ScreenCloth"
        }
      ]
    },
    "ScreenCloth": {
      "additionalProperties": false,
      "properties": {
        "shortwave_transmittance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Shortwave Transmittance",
          "type": "number"
        },
        "shortwave_reflectance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Shortwave Reflectance",
          "type": "number"
        },
        "longwave_emissivity": {
          "maximum": 1,
          "minimum": 0,
          "title": "Longwave Emissivity",
          "type": "number"
        },
        "longwave_transmittance": {
          "maximum": 1,
          "minimum": 0,
          "title": "Longwave Transmittance",
          "type": "number"
        },
        "air_permeability_m3_m2_s_k": {
          "minimum": 0,
          "title": "Air Permeability M3 M2 S K",
          "type": "number"
        },
        "thickness_m": {
          "exclusiveMinimum": 0,
          "title": "Thickness M",
          "type": "number"
        },
        "volumetric_heat_capacity_j_m3_k": {
          "exclusiveMinimum": 0,
          "maximum": 4180000,
          "title": "Volumetric Heat Capacity J M3 K",
          "type": "number"
        }
      },
      "required": [
        "shortwave_transmittance",
        "shortwave_reflectance",
        "longwave_emissivity",
        "longwave_transmittance",
        "air_permeability_m3_m2_s_k",
        "thickness_m",
        "volumetric_heat_capacity_j_m3_k"
      ],
      "title": "ScreenCloth",
      "type": "object"
    },
    "ScreenClothName": {
      "enum": [
        "thermal_screen_cloth"
      ],
      "title": "ScreenClothName",
      "type": "string"
    },
    "ScreenKind": {
      "enum": [
        "thermal",
        "shading",
        "blackout"
      ],
      "title": "ScreenKind",
      "type": "string"
    },
    "Screens": {
      "items": {
        "$ref": "#/$defs/Screen"
      },
      "minItems": 1,
      "type": "array"
    },
    "Sensor": {
      "oneOf": [
        {
          "$ref": "#/$defs/PointSensor"
        },
        {
          "$ref": "#/$defs/Camera"
        }
      ]
    },
    "Slab": {
      "additionalProperties": false,
      "properties": {
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
        "material": {
          "$ref": "#/$defs/Material",
          "default": "substrate"
        }
      },
      "required": [
        "width",
        "height",
        "material"
      ],
      "title": "Slab",
      "type": "object"
    },
    "Strip": {
      "additionalProperties": false,
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
    "Temperature": {
      "maximum": 60,
      "minimum": -60,
      "type": "number"
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
    "TrayPrimitive": {
      "additionalProperties": false,
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
        "material",
        "obstructs",
        "primitive",
        "kind",
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
        "material",
        "obstructs",
        "primitive",
        "kind",
        "start",
        "end",
        "width"
      ],
      "title": "WalkwayPrimitive",
      "type": "object"
    },
    "WallBoundary": {
      "oneOf": [
        {
          "$ref": "#/$defs/OnTheOutside"
        },
        {
          "$ref": "#/$defs/OnASpace"
        },
        {
          "$ref": "#/$defs/OnNothing"
        }
      ]
    },
    "WallId": {
      "enum": [
        "side_wall_right",
        "side_wall_left",
        "end_wall_front",
        "end_wall_back"
      ],
      "type": "string"
    },
    "Zone": {
      "additionalProperties": false,
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
      "enum": [
        "service",
        "keep_out"
      ],
      "title": "ZoneKind",
      "type": "string"
    }
  },
  "properties": {
    "schema_version": {
      "default": 7,
      "title": "Schema Version",
      "type": "integer"
    },
    "installation": {
      "$ref": "#/$defs/Installation"
    },
    "findings": {
      "items": {
        "$ref": "#/$defs/Finding"
      },
      "title": "Findings",
      "type": "array"
    },
    "draft": {
      "anyOf": [
        {
          "$ref": "#/$defs/DraftRevision"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": [
    "schema_version",
    "installation",
    "findings"
  ],
  "title": "Assessed",
  "type": "object"
};
