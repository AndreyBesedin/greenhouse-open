// Generated from greenhouse_sim/services/observations.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const OBSERVATIONS_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
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
    "Instant": {
      "format": "date-time",
      "type": "string"
    },
    "Observation": {
      "properties": {
        "observation_id": {
          "title": "Observation Id",
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
        "plant_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Plant Id"
        },
        "timestamp": {
          "$ref": "#/$defs/Instant"
        },
        "observation_type": {
          "$ref": "#/$defs/ObservationType"
        },
        "value": {
          "title": "Value",
          "type": "number"
        },
        "source": {
          "$ref": "#/$defs/RecordSource"
        },
        "sensor_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sensor Id"
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
        "quality": {
          "items": {
            "type": "string"
          },
          "title": "Quality",
          "type": "array"
        }
      },
      "required": [
        "observation_id",
        "greenhouse_id",
        "compartment_id",
        "plant_id",
        "timestamp",
        "observation_type",
        "value",
        "source"
      ],
      "title": "Observation",
      "type": "object"
    },
    "ObservationType": {
      "description": "What an Observation measures. The value doubles as the unit-bearing\nfield name on the reconstructed state models (EnvironmentState,\nGreenhouseEnvironmentState), so a new greenhouse-level type is one enum\nmember plus one optional field, no mapping table.\n\nPlant-level readings come from a sensor or vision pass on one plant;\ngreenhouse-level readings (plant_id None) describe the compartment's\nclimate, its control state, or a manual sample across plants. Recorded\nsetpoints are observations of what the controller was asked to do, not\nevents: they are continuous 5-minute state, not discrete interventions.",
      "enum": [
        "soil_moisture_pct",
        "visible_fruit_count",
        "ripe_fruit_count",
        "estimated_ripe_mass_g",
        "visible_height_cm",
        "plant_height_cm",
        "leaf_count",
        "leaf_length_cm",
        "leaf_width_cm",
        "truss_count",
        "open_flower_count",
        "green_fruit_count",
        "coloured_fruit_count",
        "air_temperature_c",
        "relative_humidity_pct",
        "humidity_deficit_g_m3",
        "co2_ppm",
        "par_umol_m2_s",
        "air_speed_m_s",
        "heating_pipe_temperature_c",
        "energy_screen_position_pct",
        "blackout_screen_position_pct",
        "window_position_lee_pct",
        "window_position_wind_pct",
        "lamps_activation_pct",
        "heating_temperature_setpoint_c",
        "ventilation_temperature_setpoint_c",
        "co2_setpoint_ppm",
        "humidity_deficit_setpoint_g_m3",
        "lamps_activation_setpoint_pct",
        "energy_screen_setpoint_pct",
        "blackout_screen_setpoint_pct",
        "irrigation_interval_setpoint_min",
        "minimum_pipe_temperature_setpoint_c",
        "minimum_window_position_lee_setpoint_pct",
        "heating_temperature_effective_c",
        "ventilation_temperature_lee_effective_c",
        "ventilation_temperature_wind_effective_c",
        "co2_effective_ppm",
        "humidity_deficit_effective_g_m3",
        "energy_screen_effective_pct",
        "blackout_screen_effective_pct",
        "irrigation_interval_effective_min",
        "minimum_pipe_temperature_effective_c",
        "minimum_window_position_lee_effective_pct",
        "co2_dosing_on",
        "co2_dosing_minutes_since_reset",
        "heating_energy_increment_mj_m2",
        "lighting_electricity_increment_kwh_m2",
        "co2_dosed_increment_kg_m2",
        "heating_cost_increment_eur_m2",
        "lighting_cost_increment_eur_m2",
        "co2_cost_increment_eur_m2",
        "fixed_cost_increment_eur_m2",
        "irrigation_flow_duration_min",
        "drain_water_volume_l_m2",
        "drain_ec_ds_m",
        "drain_ph",
        "sampled_fruit_count_per_plant",
        "sampled_fruit_fresh_weight_g_per_plant",
        "plant_density_per_m2",
        "outside_air_temperature_c",
        "outside_relative_humidity_pct",
        "outside_humidity_deficit_g_m3",
        "outside_absolute_humidity_g_m3",
        "outside_global_radiation_w_m2",
        "outside_radiation_sum_j_cm2",
        "outside_wind_speed_m_s",
        "outside_wind_direction_deg",
        "outside_barometric_pressure_hpa",
        "outside_cloud_cover_pct",
        "outside_rain",
        "outside_par_umol_m2_s",
        "outside_heat_emission_w_m2",
        "outside_co2_ppm",
        "forecast_radiation_sum_today_j_cm2"
      ],
      "title": "ObservationType",
      "type": "string"
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
  "description": "A run's observation log up to a moment: what its point sensors\nobserved, in the order delivered, whether each is fresh, and the frames\nits cameras took; the run that produced them, and when it started.",
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
    "observations": {
      "items": {
        "$ref": "#/$defs/Observation"
      },
      "title": "Observations",
      "type": "array"
    },
    "freshness": {
      "items": {
        "$ref": "#/$defs/SensorFreshness"
      },
      "title": "Freshness",
      "type": "array"
    },
    "frames": {
      "items": {
        "$ref": "#/$defs/CameraFrame"
      },
      "title": "Frames",
      "type": "array"
    }
  },
  "required": [
    "run_id",
    "start",
    "observations",
    "freshness",
    "frames"
  ],
  "title": "SensorObservations",
  "type": "object"
};
