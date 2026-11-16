// Generated from greenhouse_sim/services/parameter_set_listed.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * A set as a model's list shows it: its model, name and version, its
 * digest, what it is based on, the model version and cultivar it was made
 * for, its description, and whether it is its model's published set.
 */
export interface SetListed {
  model: string;
  name: string;
  version: number;
  digest: string;
  based_on: SetNamed | null;
  made_for: number;
  cultivar: string | null;
  description: string;
  published: boolean;
}
/**
 * A set as another names it: its name, its version and its digest.
 */
export interface SetNamed {
  name: string;
  version: number;
  digest: string;
}
