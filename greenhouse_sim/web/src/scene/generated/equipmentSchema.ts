// Generated from greenhouse_sim/services/equipment.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const EQUIPMENT_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ThermostatAt": {
      "properties": {
        "actuator_id": {
          "title": "Actuator Id",
          "type": "string"
        },
        "setpoint_c": {
          "title": "Setpoint C",
          "type": "number"
        },
        "day_c": {
          "title": "Day C",
          "type": "number"
        },
        "night_c": {
          "title": "Night C",
          "type": "number"
        },
        "runs": {
          "title": "Runs",
          "type": "boolean"
        }
      },
      "required": [
        "actuator_id",
        "setpoint_c",
        "day_c",
        "night_c",
        "runs"
      ],
      "title": "ThermostatAt",
      "type": "object"
    }
  },
  "properties": {
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "levels": {
      "additionalProperties": {
        "type": "number"
      },
      "title": "Levels",
      "type": "object"
    },
    "thermostat": {
      "anyOf": [
        {
          "$ref": "#/$defs/ThermostatAt"
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "required": [
    "time_s",
    "levels",
    "thermostat"
  ],
  "title": "EquipmentAt",
  "type": "object"
};
