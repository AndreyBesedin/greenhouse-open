// Generated from greenhouse_sim/climate/house.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * The house's air through a climate run, and through the same run with
 * everything off, at each of its moments, in seconds.
 */
export interface HouseTrace {
  times_s: number[];
  controlled: HouseSeries;
  all_off: HouseSeries;
}
/**
 * The house's air at each moment of a trace: its temperature (°C),
 * relative humidity (%) and CO₂ (ppm), and the water it has lost to
 * equipment and to condensation so far (kg).
 */
export interface HouseSeries {
  temperature_c: number[];
  humidity_pct: number[];
  co2_ppm: number[];
  removed_kg: number[];
  condensed_kg: number[];
}
