// Generated from greenhouse_sim/climate/openings.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * What each open door and vent passes at a moment of a run.
 */
export interface OpeningsAt {
  time_s: number;
  openings: OpeningFlow[];
}
/**
 * What an open door or vent passes: its net flow into the house (m³/s,
 * negative out), and what it exchanges each way besides.
 */
export interface OpeningFlow {
  opening_id: string;
  net_m3_s: number;
  exchange_m3_s: number;
}
