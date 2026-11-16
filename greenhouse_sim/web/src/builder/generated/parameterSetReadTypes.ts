// Generated from greenhouse_sim/services/parameter_set_read.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * A set as it is read: as listed, with the values it changes from its
 * base and why each, and every value it resolves to, by its model's
 * parameters' fields.
 */
export interface SetRead {
  model: string;
  name: string;
  version: number;
  digest: string;
  based_on: SetNamed | null;
  made_for: number;
  cultivar: string | null;
  description: string;
  published: boolean;
  parameters: {
    [k: string]: number;
  };
  why: {
    [k: string]: string;
  };
  values: {
    [k: string]: number;
  };
}
/**
 * A set as another names it: its name, its version and its digest.
 */
export interface SetNamed {
  name: string;
  version: number;
  digest: string;
}
