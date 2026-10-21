// Generated from greenhouse_sim/services/live.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * Where a run stands: its frame's sequence, simulated day and instant,
 * and whether it plays, and how fast.
 */
export interface LiveState {
  sequence: number;
  day: number;
  timestamp: string;
  playing: boolean;
  speed: number;
}
