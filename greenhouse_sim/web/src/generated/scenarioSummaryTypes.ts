// Generated from greenhouse_sim/services/scenario_summary.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type CropGrownBy = "plants" | "area";
export type Level = number;

export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  plants: number;
  duration_days: number;
  crop_model: string;
  crop_grown_by: CropGrownBy;
  daily: DailyCommand[];
  openings: string[];
  opening_day: number | null;
  layouts: string[];
  weathers: string[];
  thermostat: string | null;
  parameter_set: ScenarioSet | null;
}
/**
 * Set one piece of equipment to a level at a time of day, every day of
 * a run.
 */
export interface DailyCommand {
  time_of_day_s: number;
  actuator_id: string;
  level: Level;
}
/**
 * The parameter set a scenario's crop grows with, by name and version,
 * as its summary gives it (P20.5), and why its runs take no other, if they
 * take none; a scenario registered from a draft or a file runs under
 * another as a scenario of its own (`services.scenario_sets`).
 */
export interface ScenarioSet {
  name: string;
  version: number;
  fixed: string | null;
}
