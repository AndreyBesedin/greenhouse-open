// Generated from greenhouse_sim/services/playback.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * Where a playback stands: the run it plays, its layout and its epoch,
 * its clock, both as the instant it has reached and as seconds into the
 * run, as the viewer asks for a moment; whether it plays and how fast; and
 * how far ahead of it the run's records are worked out.
 */
export interface PlaybackState {
  scenario_id: string;
  run_id: string;
  layout: string;
  epoch: number;
  greenhouse_id: string;
  started_at: string;
  simulated_now: string;
  time_s: number;
  day: number;
  playing: boolean;
  seconds_per_day: number;
  worked_out_s: number;
  every_s: number;
}
