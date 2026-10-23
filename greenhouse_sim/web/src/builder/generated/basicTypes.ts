// Generated from greenhouse_sim/builder/basic.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * How a scenario's run grows its crop: by the simple daily model,
 * through the engine, or organ by organ (`greenhouse_sim.core.crop`).
 */
export type CropModel = "simple" | "organ";

/**
 * The values of the builder's first form, in metres. Each field's title
 * is the form's label for it, and the schema's example the house the form
 * starts from.
 */
export interface BasicSetup {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  installation_id: string;
  name: string;
  length_m: number;
  width_m: number;
  eave_height_m: number;
  ridge_height_m: number;
  spans?: number;
  bays?: number;
  rows: number;
  plants_per_row: number;
  plant_pitch_m: number;
  row_spacing_m: number;
  support_height_m: number;
  crop_model: CropModel;
  variety: string;
}
