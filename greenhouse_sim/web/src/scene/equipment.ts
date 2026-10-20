import { loadJson } from "../loadJson";
import { type RunParts, runParameters, scenarioUrl } from "./run";

/** A run's thermostat at a moment (P10.3): the heater it runs, the
 * temperature it heats the house's air to then, and whether it runs the
 * heater then, or a command to the heater has taken it over. */
export interface ThermostatAt {
  actuatorId: string;
  setpointC: number;
  runs: boolean;
}

/** A run's equipment at a moment, as the simulator has it
 * (`GET .../climate/equipment`): each piece's level, a thermostat's heater
 * as the house's air has it run, which the viewer cannot work out from the
 * run's commands; and the thermostat, if it has one. */
export interface EquipmentAt {
  timeS: number;
  levels: Record<string, number>;
  thermostat: ThermostatAt | null;
}

export type EquipmentState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; equipment: EquipmentAt };

/** Where a run's equipment at the moment drawn is published, asked for as
 * the climate is. */
export function equipmentUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "climate/equipment", runParameters(run));
}

function isThermostat(value: unknown): boolean {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const { actuator_id, setpoint_c, runs } = value as Record<string, unknown>;
  return (
    typeof actuator_id === "string" && typeof setpoint_c === "number" && typeof runs === "boolean"
  );
}

/** A run's equipment at a moment, checked rather than trusted. */
export function parseEquipment(body: unknown): EquipmentAt {
  const refused = new Error("the run's equipment is not what the viewer expects");
  if (typeof body !== "object" || body === null) {
    throw refused;
  }
  const { time_s, levels, thermostat } = body as Record<string, unknown>;
  if (
    typeof time_s !== "number" ||
    typeof levels !== "object" ||
    levels === null ||
    !Object.values(levels).every((level) => typeof level === "number") ||
    !(thermostat === null || isThermostat(thermostat))
  ) {
    throw refused;
  }
  const at = thermostat as { actuator_id: string; setpoint_c: number; runs: boolean } | null;
  return {
    timeS: time_s,
    levels: levels as Record<string, number>,
    thermostat:
      at === null ? null : { actuatorId: at.actuator_id, setpointC: at.setpoint_c, runs: at.runs },
  };
}

/** Fetches a run's equipment at a moment; every failure becomes a state. */
export async function loadEquipment(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<EquipmentState> {
  const answer = await loadJson(url, parseEquipment, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", equipment: answer.value } : answer;
}

/** The thermostat that runs its heater at the moment, if one does. */
export function runningThermostat(state: EquipmentState): ThermostatAt | null {
  return state.status === "loaded" && state.equipment.thermostat?.runs === true
    ? state.equipment.thermostat
    : null;
}

/** The levels a thermostat runs at the moment, which the scene is drawn
 * with: its heater's, while it runs it; none otherwise. */
export function governedLevels(state: EquipmentState): Record<string, number> {
  const thermostat = runningThermostat(state);
  if (thermostat === null || state.status !== "loaded") {
    return {};
  }
  const level = state.equipment.levels[thermostat.actuatorId];
  return level === undefined ? {} : { [thermostat.actuatorId]: level };
}
