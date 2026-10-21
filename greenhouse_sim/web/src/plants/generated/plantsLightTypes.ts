// Generated from greenhouse_sim/services/plants_light.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * The light on each of a scenario's plants at a moment of a run, in
 * seconds from its start: its PAR then, in µmol/m²/s, and its daily light
 * integral on the day the moment belongs to (`greenhouse_sim.core.clock`),
 * in mol/m²/d, by plant.
 */
export interface PlantsLight {
  time_s: number;
  par_umol_m2_s: {
    [k: string]: number;
  };
  daily_light_integral_mol_m2_d: {
    [k: string]: number;
  };
}
