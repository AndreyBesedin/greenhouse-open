// Generated from greenhouse_sim/services/position.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Status = "queued" | "running" | "finished" | "failed" | "interrupted";

/**
 * Where a position stands over its epoch: the epoch, the moment, both as
 * an instant and as seconds into the run (as the viewer asks for a moment),
 * whether it plays or follows, how far the epoch is committed, and the
 * changes given to it, as its plan holds them, spelled as a run's `&targets=`,
 * `&schedule=` and `&crop=` write them, for the viewer to draw it under.
 */
export interface PositionState {
  position_id: string;
  scenario_id: string;
  run_id: string;
  epoch: number;
  layout: string;
  seed: number | null;
  status: Status;
  started_at: string;
  simulated_now: string;
  time_s: number;
  day: number;
  playing: boolean;
  following: boolean;
  seconds_per_day: number;
  frontier_s: number;
  duration_s: number | null;
  targets: [number, string, number][];
  commands: [number, string, number][];
  crop: [number, string, string, string][];
}
