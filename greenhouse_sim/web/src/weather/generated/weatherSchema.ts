// Generated from greenhouse_sim/services/weather.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const WEATHER_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "Bearing": {
      "exclusiveMaximum": 360,
      "minimum": 0,
      "type": "number"
    },
    "OutsideLight": {
      "additionalProperties": false,
      "properties": {
        "ghi_w_m2": {
          "minimum": 0,
          "title": "Ghi W M2",
          "type": "number"
        },
        "dni_w_m2": {
          "minimum": 0,
          "title": "Dni W M2",
          "type": "number"
        },
        "dhi_w_m2": {
          "minimum": 0,
          "title": "Dhi W M2",
          "type": "number"
        },
        "par_umol_m2_s": {
          "minimum": 0,
          "title": "Par Umol M2 S",
          "type": "number"
        }
      },
      "required": [
        "ghi_w_m2",
        "dni_w_m2",
        "dhi_w_m2",
        "par_umol_m2_s"
      ],
      "title": "OutsideLight",
      "type": "object"
    },
    "Percent": {
      "maximum": 100,
      "minimum": 0,
      "type": "number"
    },
    "Site": {
      "additionalProperties": false,
      "properties": {
        "latitude_deg": {
          "maximum": 90,
          "minimum": -90,
          "title": "Latitude Deg",
          "type": "number"
        },
        "longitude_deg": {
          "maximum": 180,
          "minimum": -180,
          "title": "Longitude Deg",
          "type": "number"
        },
        "elevation_m": {
          "default": 0,
          "title": "Elevation M",
          "type": "number"
        },
        "time_zone": {
          "title": "Time Zone",
          "type": "string"
        },
        "x_bearing_deg": {
          "$ref": "#/$defs/Bearing",
          "default": 90
        }
      },
      "required": [
        "latitude_deg",
        "longitude_deg",
        "elevation_m",
        "time_zone",
        "x_bearing_deg"
      ],
      "title": "Site",
      "type": "object"
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
    "site": {
      "$ref": "#/$defs/Site"
    },
    "moment": {
      "format": "date-time",
      "title": "Moment",
      "type": "string"
    },
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "weather": {
      "$ref": "#/$defs/WeatherState"
    },
    "wind_m_s": {
      "$ref": "#/$defs/Vector3"
    },
    "sun": {
      "$ref": "#/$defs/SunPosition"
    },
    "sun_direction": {
      "$ref": "#/$defs/Vector3"
    },
    "light": {
      "$ref": "#/$defs/OutsideLight"
    }
  },
  "required": [
    "site",
    "moment",
    "time_s",
    "weather",
    "wind_m_s",
    "sun",
    "sun_direction",
    "light"
  ],
  "title": "WeatherAtAMoment",
  "type": "object"
};
