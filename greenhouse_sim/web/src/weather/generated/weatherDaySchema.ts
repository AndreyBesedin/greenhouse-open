// Generated from greenhouse_sim/services/weather_day.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const WEATHER_DAY_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "Bearing": {
      "exclusiveMaximum": 360,
      "minimum": 0,
      "type": "number"
    },
    "Percent": {
      "maximum": 100,
      "minimum": 0,
      "type": "number"
    },
    "SunPosition": {
      "additionalProperties": false,
      "properties": {
        "elevation_deg": {
          "title": "Elevation Deg",
          "type": "number"
        },
        "azimuth_deg": {
          "title": "Azimuth Deg",
          "type": "number"
        },
        "declination_deg": {
          "title": "Declination Deg",
          "type": "number"
        },
        "equation_of_time_min": {
          "title": "Equation Of Time Min",
          "type": "number"
        }
      },
      "required": [
        "elevation_deg",
        "azimuth_deg",
        "declination_deg",
        "equation_of_time_min"
      ],
      "title": "SunPosition",
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
    "WeatherState": {
      "additionalProperties": false,
      "properties": {
        "air_temperature_c": {
          "default": 10,
          "title": "Air Temperature C",
          "type": "number"
        },
        "relative_humidity_pct": {
          "$ref": "#/$defs/Percent",
          "default": 80
        },
        "co2_ppm": {
          "default": 420,
          "exclusiveMinimum": 0,
          "title": "Co2 Ppm",
          "type": "number"
        },
        "wind_speed_m_s": {
          "default": 0,
          "minimum": 0,
          "title": "Wind Speed M S",
          "type": "number"
        },
        "wind_direction_deg": {
          "anyOf": [
            {
              "$ref": "#/$defs/Bearing"
            },
            {
              "type": "null"
            }
          ],
          "default": 0
        },
        "global_radiation_w_m2": {
          "default": 0,
          "minimum": 0,
          "title": "Global Radiation W M2",
          "type": "number"
        },
        "cloud_cover_pct": {
          "$ref": "#/$defs/Percent",
          "default": 0
        },
        "barometric_pressure_hpa": {
          "exclusiveMinimum": 0,
          "title": "Barometric Pressure Hpa",
          "type": "number"
        }
      },
      "required": [
        "air_temperature_c",
        "relative_humidity_pct",
        "co2_ppm",
        "wind_speed_m_s",
        "wind_direction_deg",
        "global_radiation_w_m2",
        "cloud_cover_pct",
        "barometric_pressure_hpa"
      ],
      "title": "WeatherState",
      "type": "object"
    }
  },
  "properties": {
    "start": {
      "format": "date-time",
      "title": "Start",
      "type": "string"
    },
    "every_s": {
      "title": "Every S",
      "type": "number"
    },
    "times_s": {
      "items": {
        "type": "number"
      },
      "title": "Times S",
      "type": "array"
    },
    "weather": {
      "items": {
        "$ref": "#/$defs/WeatherState"
      },
      "title": "Weather",
      "type": "array"
    },
    "sun": {
      "items": {
        "$ref": "#/$defs/SunPosition"
      },
      "title": "Sun",
      "type": "array"
    },
    "sun_directions": {
      "items": {
        "$ref": "#/$defs/Vector3"
      },
      "title": "Sun Directions",
      "type": "array"
    }
  },
  "required": [
    "start",
    "every_s",
    "times_s",
    "weather",
    "sun",
    "sun_directions"
  ],
  "title": "WeatherThroughADay",
  "type": "object"
};
