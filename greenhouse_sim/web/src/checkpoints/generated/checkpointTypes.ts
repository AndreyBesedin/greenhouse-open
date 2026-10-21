// Generated from greenhouse_sim/services/checkpoint.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * @minItems 3
 * @maxItems 3
 */
export type Commanded = [number, string, number];

/**
 * A checkpoint as a client lists it: its identifier, its run's parts,
 * its day and moment, and how many plants it keeps.
 */
export interface CheckpointSummary {
  checkpoint_id: string;
  scenario_id: string;
  layout: string;
  weather: string;
  levels: {
    [k: string]: number;
  };
  openings: {
    [k: string]: number;
  };
  commands: Commanded[];
  daily: Commanded[] | null;
  targets: Commanded[];
  day: number;
  time_s: number;
  plants: number;
}
