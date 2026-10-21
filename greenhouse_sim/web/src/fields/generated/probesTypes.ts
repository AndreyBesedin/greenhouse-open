// Generated from greenhouse_sim/climate/probes.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * Probes through a climate run, at each of its moments, in seconds.
 */
export interface ClimateProbes {
  times_s: number[];
  probes: ProbeSeries[];
}
/**
 * A probe's point, and what it reads through the run and through the
 * same run with everything off.
 */
export interface ProbeSeries {
  point: Vector3;
  controlled: Readings;
  all_off: Readings;
}
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}
/**
 * A probe's readings at each moment: temperature (°C), relative humidity
 * (%) and air speed (m/s).
 */
export interface Readings {
  temperature_c: number[];
  humidity_pct: number[];
  speed_m_s: number[];
}
