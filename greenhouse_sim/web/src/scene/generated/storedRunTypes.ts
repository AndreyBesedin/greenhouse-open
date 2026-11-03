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
  start_s: number;
  fork: ForkOf | null;
  damaged: boolean;
}
/**
 * Where a fork comes from (decision 0065): its parent, the exact instant
 * it branches at, the state it inherits (a checkpoint at `start_s`, kept as a
 * copy of its own, and the parent's trajectory digest through it; none for
 * one from its run's start), how many entries of its log are its parent's,
 * and the layout it changes to, if it does.
 */
export interface ForkOf {
  run_id: string;
  epoch: number;
  at_s: number;
  start_s: number;
  digest: string | null;
  checkpoint_sha256: string | null;
  inherited: number;
  layout: string | null;
}
