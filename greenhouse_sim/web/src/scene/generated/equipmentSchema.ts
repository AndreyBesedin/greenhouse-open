// Generated from greenhouse_sim/services/equipment.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const EQUIPMENT_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "ThermostatAt": {
      "description": "A run's thermostat at a moment (`climate.thermostat`): the heater it\nruns, the temperature it heats the house's air to then, and whether it\nruns the heater then, or a command to the heater has taken it over.",
      "properties": {
        "actuator_id": {
          "title": "Actuator Id",
          "type": "string"
        },
        "setpoint_c": {
          "title": "Setpoint C",
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
        "runs"
      ],
      "title": "ThermostatAt",
      "type": "object"
    }
  },
  "description": "A run's equipment at a moment: each piece's level, as its commands set\nit and its thermostat runs its heater, and the thermostat, if it has\none.",
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
