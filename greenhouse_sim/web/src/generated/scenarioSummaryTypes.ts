// Generated from greenhouse_sim/services/scenario_summary.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Level = number;

export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  plants: number;
  duration_days: number;
  crop_model: string;
  daily: DailyCommand[];
  openings: string[];
  opening_day: number | null;
  layouts: string[];
  weathers: string[];
  thermostat: string | null;
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
