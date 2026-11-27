// Generated from greenhouse_sim/services/area_crop.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * The area a crop model's quantities are per m² of: a scope's floor,
 * its share of the house's, or its cultivated area, the ground its
 * planting positions take.
 */
export type AreaBasis = "floor" | "cultivated";

/**
 * A run's crop grown by area `time_s` into it, through the days ended
 * by then: its model, by its registry's name and in words
 * (`model_name`), the basis its quantities are per m² of, the quantities
 * charted, in order, the days, from 0, and, for each day, each scope's
 * values (`scopes`, in the rows' order) and the house's (`house`), by
 * quantity's key.
 */
export interface AreaCropCourse {
  time_s: number;
  model: string;
  model_name: string;
  basis: AreaBasis;
  quantities: AreaQuantity[];
  days: number[];
  scopes: ScopeCourse[];
  house: {
    [k: string]: number[];
  };
}
/**
 * A quantity of a crop grown by area that a viewer charts (decision
 * 0083): its `key` in what a state reads, its name, and its unit, the
 * model's own: per m² of its basis, or a plant's nodes, a temperature or a
 * temperature sum. A model's quantities keep its units, never converted to
 * another model's (decision 0062).
 */
export interface AreaQuantity {
  key: string;
  name: string;
  unit: string;
}
/**
 * One scope of a crop grown by area through a run's days: its
 * identifier, its area on its model's basis, in m², and its values, by
 * quantity's key, one for each day, at the day's start.
 */
export interface ScopeCourse {
  scope_id: string;
  area_m2: number;
  values: {
    [k: string]: number[];
  };
}
