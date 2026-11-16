// Generated from greenhouse_sim/services/parameter_set_comparison.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * Two sets of one model, by name, version and digest, and each
 * parameter they give apart, in their model's order.
 */
export interface SetComparison {
  first: SetNamed;
  second: SetNamed;
  changes: ParameterChange[];
}
/**
 * A set as another names it: its name, its version and its digest.
 */
export interface SetNamed {
  name: string;
  version: number;
  digest: string;
}
/**
 * A parameter whose values two sets give apart.
 */
export interface ParameterChange {
  name: string;
  first: number;
  second: number;
}
