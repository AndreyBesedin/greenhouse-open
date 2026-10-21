// Generated from greenhouse_sim/services/run_state.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const RUN_STATE_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "CameraAt": {
      "description": "Where a camera stands with its frames at a moment of a run: how many\nit has taken since the run's start, and its latest, if any.",
      "properties": {
        "sensor_id": {
          "title": "Sensor Id",
          "type": "string"
        },
        "frames": {
          "title": "Frames",
          "type": "integer"
        },
        "latest": {
          "anyOf": [
            {
              "$ref": "#/$defs/CameraFrame"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "sensor_id",
        "frames",
        "latest"
      ],
      "title": "CameraAt",
      "type": "object"
    },
    "CameraFrame": {
      "description": "A frame a camera took: when, from where, turned how, with what\nintrinsics, and what images it holds.",
      "properties": {
        "frame_id": {
          "title": "Frame Id",
          "type": "string"
        },
        "greenhouse_id": {
          "title": "Greenhouse Id",
          "type": "string"
        },
        "compartment_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Compartment Id"
        },
        "sensor_id": {
          "title": "Sensor Id",
          "type": "string"
        },
        "timestamp": {
          "$ref": "#/$defs/Instant"
        },
        "pose": {
          "$ref": "#/$defs/CameraPose"
        },
        "intrinsics": {
          "$ref": "#/$defs/CameraIntrinsics"
        },
        "modalities": {
          "items": {
            "$ref": "#/$defs/CaptureModality"
          },
          "minItems": 1,
          "title": "Modalities",
          "type": "array"
        },
        "source": {
          "$ref": "#/$defs/RecordSource"
        },
        "delivered_at": {
          "anyOf": [
            {
              "$ref": "#/$defs/Instant"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "capture_ids": {
          "default": [],
          "items": {
            "type": "string"
          },
          "title": "Capture Ids",
          "type": "array"
        }
      },
      "required": [
        "frame_id",
        "greenhouse_id",
        "compartment_id",
        "sensor_id",
        "timestamp",
        "pose",
        "intrinsics",
        "modalities",
        "source",
        "delivered_at",
        "capture_ids"
      ],
      "title": "CameraFrame",
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
        "ppy",
        "distortion"
      ],
      "title": "CameraIntrinsics",
      "type": "object"
    },
    "CameraPose": {
      "description": "Where a camera stood, and how it was turned, in its greenhouse's\nframe: x along the house, y across it and z up, in metres, from a corner\nof its floor. The rotation, a unit quaternion (w, x, y, z), turns the\ncamera's own frame into the greenhouse's. In the camera's frame x runs\nalong the way it looks, y to its left and z up, so its picture's u runs\nagainst y and its v against z. The optical convention, z along the way\nit looks, x right and y down, is a fixed turn away.",
      "properties": {
        "x_m": {
          "title": "X M",
          "type": "number"
        },
        "y_m": {
          "title": "Y M",
          "type": "number"
        },
        "z_m": {
          "title": "Z M",
          "type": "number"
        },
        "qw": {
          "title": "Qw",
          "type": "number"
        },
        "qx": {
          "title": "Qx",
          "type": "number"
        },
        "qy": {
          "title": "Qy",
          "type": "number"
        },
        "qz": {
          "title": "Qz",
          "type": "number"
        }
      },
      "required": [
        "x_m",
        "y_m",
        "z_m",
        "qw",
        "qx",
        "qy",
        "qz"
      ],
      "title": "CameraPose",
      "type": "object"
    },
    "CaptureModality": {
      "description": "What a MediaCapture recorded. The WUR canopy cameras (Oak-D S2 POE)\nwrite an RGB image, a depth image aligned to it, and the left and right\ninfrared images the depth was computed from.",
      "enum": [
        "RGB",
        "DEPTH",
        "INFRARED_LEFT",
        "INFRARED_RIGHT"
      ],
      "title": "CaptureModality",
      "type": "string"
    },
    "Command": {
      "additionalProperties": false,
      "description": "Set one piece of equipment to a level, at a moment.",
      "properties": {
        "time_s": {
          "minimum": 0,
          "title": "Time S",
          "type": "number"
        },
        "actuator_id": {
          "title": "Actuator Id",
          "type": "string"
        },
        "level": {
          "$ref": "#/$defs/Level"
        }
      },
      "required": [
        "time_s",
        "actuator_id",
        "level"
      ],
      "title": "Command",
      "type": "object"
    },
    "Freshness": {
      "description": "Where a point sensor stands, at a moment, with its readings.",
      "enum": [
        "waiting",
        "fresh",
        "stale",
        "unavailable"
      ],
      "title": "Freshness",
      "type": "string"
    },
    "HouseAirNow": {
      "description": "The house's air as one well-mixed volume at a moment.",
      "properties": {
        "temperature_c": {
          "title": "Temperature C",
          "type": "number"
        },
        "humidity_pct": {
          "title": "Humidity Pct",
          "type": "number"
        },
        "co2_ppm": {
          "title": "Co2 Ppm",
          "type": "number"
        }
      },
      "required": [
        "temperature_c",
        "humidity_pct",
        "co2_ppm"
      ],
      "title": "HouseAirNow",
      "type": "object"
    },
    "Instant": {
      "format": "date-time",
      "type": "string"
    },
    "Level": {
      "maximum": 1,
      "minimum": 0,
      "type": "number"
    },
    "RecordSource": {
      "description": "Where a piece of domain data came from - the system/run that\nproduced it (SIMULATION, REAL_SENSORS, ...) plus, where meaningful, the\nid of that specific run/sensor/import (source_id) so the record stays\ntraceable without requiring the record itself to carry a simulation-\nspecific identity.",
      "properties": {
        "type": {
          "$ref": "#/$defs/SourceType"
        },
        "source_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Id"
        }
      },
      "required": [
        "type",
        "source_id"
      ],
      "title": "RecordSource",
      "type": "object"
    },
    "SensorFreshness": {
      "description": "Whether a point sensor's latest reading due by a moment has come.",
      "properties": {
        "sensor_id": {
          "title": "Sensor Id",
          "type": "string"
        },
        "state": {
          "$ref": "#/$defs/Freshness"
        },
        "due_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Due At"
        },
        "latest_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Latest At"
        }
      },
      "required": [
        "sensor_id",
        "state",
        "due_at",
        "latest_at"
      ],
      "title": "SensorFreshness",
      "type": "object"
    },
    "SourceType": {
      "enum": [
        "SIMULATION",
        "REAL_SENSORS",
        "EXTERNAL_API",
        "IMPORTED_DATA"
      ],
      "title": "SourceType",
      "type": "string"
    }
  },
  "description": "What each process of a run holds at a moment.",
  "properties": {
    "run_id": {
      "title": "Run Id",
      "type": "string"
    },
    "start": {
      "format": "date-time",
      "title": "Start",
      "type": "string"
    },
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "day": {
      "title": "Day",
      "type": "integer"
    },
    "at": {
      "format": "date-time",
      "title": "At",
      "type": "string"
    },
    "house_air": {
      "anyOf": [
        {
          "$ref": "#/$defs/HouseAirNow"
        },
        {
          "type": "null"
        }
      ]
    },
    "crop_model": {
      "title": "Crop Model",
      "type": "string"
    },
    "plants": {
      "title": "Plants",
      "type": "integer"
    },
    "days_lived": {
      "title": "Days Lived",
      "type": "integer"
    },
    "levels": {
      "additionalProperties": {
        "type": "number"
      },
      "title": "Levels",
      "type": "object"
    },
    "commands_given": {
      "title": "Commands Given",
      "type": "integer"
    },
    "latest_commands": {
      "items": {
        "$ref": "#/$defs/Command"
      },
      "title": "Latest Commands",
      "type": "array"
    },
    "sensors": {
      "items": {
        "$ref": "#/$defs/SensorFreshness"
      },
      "title": "Sensors",
      "type": "array"
    },
    "cameras": {
      "items": {
        "$ref": "#/$defs/CameraAt"
      },
      "title": "Cameras",
      "type": "array"
    }
  },
  "required": [
    "run_id",
    "start",
    "time_s",
    "day",
    "at",
    "house_air",
    "crop_model",
    "plants",
    "days_lived",
    "levels",
    "commands_given",
    "latest_commands",
    "sensors",
    "cameras"
  ],
  "title": "RunState",
  "type": "object"
};
