// Generated from greenhouse_sim/fields/field.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * One thing a field says about the air at a point.
 */
export type AirQuantity = "velocity" | "temperature" | "humidity" | "co2" | "pressure";

/**
 * An environment field as it is published to a viewer: its grid, and
 * each channel's values over it (see the module's description).
 */
export interface FieldDocument {
  schema_version: 1;
  field_id: string;
  source: string;
  time_s: number;
  grid: FieldGrid;
  channels: ChannelDocument[];
}
/**
 * A box divided into a regular grid of cells.
 */
export interface FieldGrid {
  origin: Vector3;
  cell_size: Vector3;
  cells: CellCounts;
}
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}
/**
 * How many cells a grid has along x, y and z.
 */
export interface CellCounts {
  x: number;
  y: number;
  z: number;
}
/**
 * One channel of a published field.
 */
export interface ChannelDocument {
  quantity: AirQuantity;
  unit: string;
  components: 1 | 3;
  encoding?: "float32-le-base64";
  data: string;
  minimum: number;
  maximum: number;
}
