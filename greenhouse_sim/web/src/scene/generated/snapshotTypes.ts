// Generated from greenhouse_sim/scene/snapshot.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type SceneEntityKind =
  | "GROUND"
  | "AXES"
  | "GREENHOUSE_BOUNDS"
  | "FLOOR"
  | "WALL"
  | "ROOF"
  | "GUTTER"
  | "FRAME"
  | "VENT"
  | "DOOR"
  | "PLANTING_POSITION"
  | "CROP_GUTTER"
  | "BENCH"
  | "SLAB"
  | "WALKWAY"
  | "SERVICE_ZONE"
  | "KEEP_OUT"
  | "RAIL"
  | "PIPE"
  | "OBSTACLE"
  | "PLANT";
export type Shape = Plane | Cylinder | Box | Polygon | Axes;
/**
 * What a fixture, or a part of the envelope, is made of.
 */
export type Material = "steel" | "aluminium" | "plastic" | "concrete" | "substrate";

/**
 * One greenhouse at one simulated day, as a viewer draws it. Positions
 * and sizes are in metres, in right-handed world axes with z up.
 */
export interface SceneSnapshot {
  schema_version: number;
  greenhouse_id: string;
  simulated_day: number;
  entities: SceneEntity[];
}
export interface SceneEntity {
  entity_id: string;
  kind: SceneEntityKind;
  transform: Transform;
  shape: Shape;
  color: Color;
  material: Material | null;
  label: string | null;
  properties: {
    [k: string]: string | number | boolean;
  };
}
/**
 * Places a shape's own frame in the world: rotate, then translate.
 */
export interface Transform {
  position: Vector3;
  rotation: Quaternion;
}
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}
/**
 * A rotation as a unit quaternion; the default is no rotation.
 */
export interface Quaternion {
  w: number;
  x: number;
  y: number;
  z: number;
}
/**
 * A flat rectangle in its frame's x-y plane, centred on its origin,
 * facing +z.
 */
export interface Plane {
  shape: "plane";
  size_x: number;
  size_y: number;
}
/**
 * An upright cylinder: its base is centred on its frame's origin and it
 * rises along +z. A height of zero is allowed: a plant can be lowered by its
 * whole visible height.
 */
export interface Cylinder {
  shape: "cylinder";
  radius: number;
  height: number;
}
/**
 * A rectangular box standing on its frame's origin: its base is centred
 * on the origin, and it rises along +z.
 */
export interface Box {
  shape: "box";
  size_x: number;
  size_y: number;
  size_z: number;
}
/**
 * A flat polygon in its frame's x-y plane, facing +z: its corners in
 * order, counter-clockwise as seen from its front, such as a greenhouse's
 * gable end.
 */
export interface Polygon {
  shape: "polygon";
  /**
   * @minItems 3
   */
  points: [Point2, Point2, Point2, ...Point2[]];
}
/**
 * A point in a shape's own x-y plane.
 */
export interface Point2 {
  x: number;
  y: number;
}
/**
 * A reference marker: one arrow from the origin along each of +x, +y and
 * +z.
 */
export interface Axes {
  shape: "axes";
  length: number;
}
/**
 * An sRGB colour, each channel from 0 to 1.
 */
export interface Color {
  r: number;
  g: number;
  b: number;
}
