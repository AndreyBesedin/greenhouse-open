// Generated from greenhouse_sim/climate/house.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const HOUSE_AIR_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "HouseSeries": {
      "additionalProperties": false,
      "description": "The house's air at each moment of a trace: its temperature (°C),\nrelative humidity (%) and CO₂ (ppm), and the water it has lost to\nequipment and to condensation so far (kg).",
      "properties": {
        "temperature_c": {
          "items": {
            "type": "number"
          },
          "title": "Temperature C",
          "type": "array"
        },
        "humidity_pct": {
          "items": {
            "type": "number"
          },
          "title": "Humidity Pct",
          "type": "array"
        },
        "co2_ppm": {
          "items": {
            "type": "number"
          },
          "title": "Co2 Ppm",
          "type": "array"
        },
        "removed_kg": {
          "items": {
            "type": "number"
          },
          "title": "Removed Kg",
          "type": "array"
        },
        "condensed_kg": {
          "items": {
            "type": "number"
          },
          "title": "Condensed Kg",
          "type": "array"
        }
      },
      "required": [
        "temperature_c",
        "humidity_pct",
        "co2_ppm",
        "removed_kg",
        "condensed_kg"
      ],
      "title": "HouseSeries",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "The house's air through a climate run, and through the same run with\neverything off, at each of its moments, in seconds.",
  "properties": {
    "times_s": {
      "items": {
        "type": "number"
      },
      "title": "Times S",
      "type": "array"
    },
    "controlled": {
      "$ref": "#/$defs/HouseSeries"
    },
    "all_off": {
      "$ref": "#/$defs/HouseSeries"
    }
  },
  "required": [
    "times_s",
    "controlled",
    "all_off"
  ],
  "title": "HouseTrace",
  "type": "object"
};
