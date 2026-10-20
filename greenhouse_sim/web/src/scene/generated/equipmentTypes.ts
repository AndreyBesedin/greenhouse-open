// Generated from greenhouse_sim/services/equipment.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * A run's equipment at a moment: each piece's level, as its commands set
 * it and its thermostat runs its heater, and the thermostat, if it has
 * one.
 */
export interface EquipmentAt {
  time_s: number;
  levels: {
    [k: string]: number;
  };
  thermostat: ThermostatAt | null;
}
/**
 * A run's thermostat at a moment (`climate.thermostat`): the heater it
 * runs, the temperature it heats the house's air to then, and whether it
 * runs the heater then, or a command to the heater has taken it over.
 */
export interface ThermostatAt {
  actuator_id: string;
  setpoint_c: number;
  runs: boolean;
}
