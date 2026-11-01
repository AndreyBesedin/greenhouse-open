// Generated from greenhouse_sim/services/stored_run.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Status = "queued" | "running" | "finished" | "failed" | "interrupted";

/**
 * An epoch as a person's list shows it: which run, whose seed, in what
 * state, and how far it is committed.
 */
export interface StoredRun {
  run_id: string;
  epoch: number;
  scenario_id: string;
  seed: number | null;
  layout: string;
  status: Status;
  frontier_s: number;
  duration_s: number | null;
  progress: number | null;
  created_at: string | null;
  size_bytes: number;
}
