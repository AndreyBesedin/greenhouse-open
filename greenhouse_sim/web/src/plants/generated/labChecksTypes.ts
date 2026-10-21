// Generated from greenhouse_sim/services/lab_checks.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * Whatever is wrong with each of the lab's plants on a run's day.
 */
export interface LabChecks {
  day: number;
  problems: {
    [k: string]: string[];
  };
}
