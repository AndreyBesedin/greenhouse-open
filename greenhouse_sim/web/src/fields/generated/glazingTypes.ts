// Generated from greenhouse_sim/climate/glazing.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * The glazing at a moment of a run: the outside's temperature, the
 * glass's U in the wind, and each glazed surface.
 */
export interface GlazingAt {
  time_s: number;
  outside_c: number;
  u_w_m2k: number;
  surfaces: SurfaceTemperature[];
}
/**
 * A glazed surface at a moment: the mean temperature of the air against
 * it, its own temperature, and the heat it passes out of the house, in
 * watts (negative in).
 */
export interface SurfaceTemperature {
  surface_id: string;
  air_c: number;
  surface_c: number;
  loss_w: number;
}
