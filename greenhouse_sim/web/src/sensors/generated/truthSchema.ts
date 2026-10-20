// Generated from greenhouse_sim/services/truth.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const TRUTH_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
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
    "SensorTruth": {
      "description": "What a perfect sensor would have read at each of a sensor's sample\nmoments, in seconds from the run's start: None where the air carries no\nsuch quantity.",
      "properties": {
        "sensor_id": {
          "title": "Sensor Id",
          "type": "string"
        },
        "observation_type": {
          "$ref": "#/$defs/ObservationType"
        },
        "unit": {
          "title": "Unit",
          "type": "string"
        },
        "times_s": {
          "items": {
            "type": "number"
          },
          "title": "Times S",
          "type": "array"
        },
        "values": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ]
          },
          "title": "Values",
          "type": "array"
        }
      },
      "required": [
        "sensor_id",
        "observation_type",
        "unit",
        "times_s",
        "values"
      ],
      "title": "SensorTruth",
      "type": "object"
    }
  },
  "description": "What each of a scenario's point sensors truly sampled up to a moment\nof a run: for evaluation and QA only.",
  "properties": {
    "run_id": {
      "title": "Run Id",
      "type": "string"
    },
    "sensors": {
      "items": {
        "$ref": "#/$defs/SensorTruth"
      },
      "title": "Sensors",
      "type": "array"
    }
  },
  "required": [
    "run_id",
    "sensors"
  ],
  "title": "SensorTruths",
  "type": "object"
};
