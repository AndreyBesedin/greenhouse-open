// Generated from greenhouse_sim/services/lab_environments.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export interface LabEnvironments {
  [k: string]: LocalEnvironment;
}
/**
 * What one plant experiences over one day, where it stands.
 */
export interface LocalEnvironment {
  mean_temperature_c: number;
  par_mol_m2_day: number;
  co2_ppm: number;
  water_status: number;
}
