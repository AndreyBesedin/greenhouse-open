// Generated from greenhouse_sim/cfd/geometry.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * What a boundary of the CFD domain is.
 */
export type BoundaryCategory = "floor" | "wall" | "ceiling" | "opening" | "obstacle";
/**
 * One of the domain's six faces, by where it lies.
 */
export type Face = "floor" | "ceiling" | "wall_front" | "wall_back" | "wall_right" | "wall_left";
export type OpeningKind = "door" | "roof_vent" | "side_vent";

/**
 * What a solver is given for a scenario: the domain, on its grid, and
 * every boundary, as they will be meshed.
 */
export interface CfdGeometry {
  schema_version?: 1;
  scenario_id: string;
  grid: FieldGrid;
  boundaries: Boundary[];
  too_small: string[];
  unplaced: string[];
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
 * One boundary of the domain as it is meshed: what it is, and the faces
 * of the mesh it is made of.
 */
export interface Boundary {
  name: string;
  category: BoundaryCategory;
  face?: Face | null;
  opening_id?: string | null;
  opening_kind?: OpeningKind | null;
  box: Box;
  mesh_faces: number;
}
/**
 * An axis-aligned box, by its lowest and highest corners.
 */
export interface Box {
  minimum: Vector3;
  maximum: Vector3;
}
