// Generated from greenhouse_sim/builder/edit.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Edit =
  | PlaceItems
  | RepeatItems
  | SpaceItems
  | PlaceOpenings
  | SpreadOpenings
  | RepeatOpenings
  | SpaceOpenings
  | SetField
  | SetValue
  | RemoveItems;
export type Equipment = Fan | Heater | Dehumidifier;
export type Sensor = PointSensor | Camera;
export type PointKind =
  | "temperature"
  | "humidity"
  | "co2"
  | "air_speed"
  | "par"
  | "outside_temperature"
  | "outside_humidity"
  | "wind_speed"
  | "wind_direction"
  | "barometric_pressure";
/**
 * What an area of the floor is kept for.
 */
export type ZoneKind = "service" | "keep_out";
export type Primitive =
  | BoxPrimitive
  | CylinderPrimitive
  | PipePrimitive
  | PipeRunPrimitive
  | RailPrimitive
  | TrayPrimitive
  | WalkwayPrimitive;
/**
 * What a fixture, or a part of the envelope, is made of.
 */
export type Material = "steel" | "aluminium" | "plastic" | "concrete" | "substrate";
/**
 * What a fixture stands in the way of.
 */
export type Obstruction = "movement" | "airflow" | "light";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind1 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind2 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind3 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind4 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind5 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
/**
 * What a fixture is, for every consumer of its geometry.
 */
export type FixtureKind6 = "crop_gutter" | "bench" | "slab" | "walkway" | "rail" | "pipe" | "wire" | "obstacle";
export type Count = number;
export type Axis = "x" | "y" | "z";
export type OpeningKind = "door" | "roof_vent" | "side_vent";
export type JsonValue = unknown;

/**
 * Pieces of equipment, sensors, zones or fixtures like `item`, the
 * first where it stands and each next `step` further, named after its
 * identifier.
 */
export interface PlaceItems {
  edit?: "place_items";
  item: Equipment | Sensor | Zone | Primitive;
  count?: number;
  step?: Vector3 | null;
}
/**
 * A fan: a rotor of a diameter, centred on `position`, blowing its rated
 * flow of air along its heading.
 */
export interface Fan {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  actuator_id: string;
  heading?: number;
  kind?: "fan";
  position: Vector3;
  diameter_m: number;
  flow_m3_s: number;
}
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}
/**
 * A unit heater: its rated power, all of it given to the air as heat.
 */
export interface Heater {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  actuator_id: string;
  heading?: number;
  base: Vector3;
  size_x: number;
  size_y: number;
  size_z: number;
  kind?: "heater";
  power_w: number;
}
/**
 * A dehumidifier: the water it takes out of the air at full power, and
 * the heat it gives the air while it does.
 */
export interface Dehumidifier {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  actuator_id: string;
  heading?: number;
  base: Vector3;
  size_x: number;
  size_y: number;
  size_z: number;
  kind?: "dehumidifier";
  removal_kg_h: number;
  heat_w: number;
}
/**
 * A sensor reading one quantity of the air at its position, or, outside
 * the house, of the weather.
 */
export interface PointSensor {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  sensor_id: string;
  position: Vector3;
  cadence_s?: number;
  kind: PointKind;
  imperfections?: Imperfections;
}
/**
 * How a sensor errs, each in its own unit; all nothing for a clean one.
 *
 * Noise is Gaussian, of a standard deviation; a reading is rounded to the
 * quantization step; a fixed bias is added, and a drift that grows linearly
 * with time since the run's start; a sample drops out with a probability;
 * and a reading is delivered a fixed time after its sample.
 */
export interface Imperfections {
  noise_sd?: number;
  quantization?: number;
  bias?: number;
  drift_per_hour?: number;
  dropout?: number;
  latency_s?: number;
}
/**
 * A camera at its position, looking at `target`, with its intrinsics.
 */
export interface Camera {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  sensor_id: string;
  position: Vector3;
  cadence_s?: number;
  kind?: "camera";
  target: Vector3;
  intrinsics: CameraIntrinsics;
}
/**
 * Pinhole intrinsics of one image stream, in pixels, with the
 * calibration's distortion coefficients exactly as given.
 */
export interface CameraIntrinsics {
  width: number;
  height: number;
  fx: number;
  fy: number;
  ppx: number;
  ppy: number;
  distortion?: number[];
}
/**
 * A service zone or keep-out volume: a strip of the floor, rising
 * `height` above it.
 */
export interface Zone {
  zone_id: string;
  kind: ZoneKind;
  area: Strip;
  height: number;
}
/**
 * A rectangle of the floor: a centre line from `start` to `end`, `width`
 * wide.
 */
export interface Strip {
  start: Point2;
  end: Point2;
  width: number;
}
/**
 * A point in a shape's own x-y plane.
 */
export interface Point2 {
  x: number;
  y: number;
}
/**
 * A box standing on the floor or anything else: its base centred on
 * `base`, turned about the vertical by `heading` radians from the
 * greenhouse's x.
 */
export interface BoxPrimitive {
  fixture_id: string;
  material?: Material | null;
  obstructs?: Obstruction[] | null;
  primitive?: "box";
  kind?: FixtureKind;
  base: Vector3;
  size_x: number;
  size_y: number;
  size_z: number;
  heading?: number;
}
/**
 * An upright cylinder, its base centred on `base`.
 */
export interface CylinderPrimitive {
  fixture_id: string;
  material?: Material | null;
  obstructs?: Obstruction[] | null;
  primitive?: "cylinder";
  kind?: FixtureKind1;
  base: Vector3;
  radius: number;
  height: number;
}
/**
 * A straight pipe, its axis from `start` to `end`.
 */
export interface PipePrimitive {
  fixture_id: string;
  material?: Material | null;
  obstructs?: Obstruction[] | null;
  primitive?: "pipe";
  kind?: FixtureKind2;
  start: Vector3;
  end: Vector3;
  radius: number;
}
/**
 * Pipes repeated in parallel, such as heating pipes stacked along a wall:
 * the first from `start` to `end`, each next one `step` further on, `count`
 * in all. Each is its own multiple of the step from the first, and is called
 * `<fixture_id>_<n>`, from 1.
 */
export interface PipeRunPrimitive {
  fixture_id: string;
  material?: Material | null;
  obstructs?: Obstruction[] | null;
  primitive?: "pipe_run";
  kind?: FixtureKind3;
  start: Vector3;
  end: Vector3;
  radius: number;
  count: number;
  step: Vector3;
}
/**
 * A rail of two parallel tubes, `gauge` apart from axis to axis, either
 * side of its centre line from `start` to `end`. Its tubes are
 * `<fixture_id>_right` and `<fixture_id>_left`, as seen looking along it.
 */
export interface RailPrimitive {
  fixture_id: string;
  material?: Material | null;
  obstructs?: Obstruction[] | null;
  primitive?: "rail";
  kind?: FixtureKind4;
  start: Vector3;
  end: Vector3;
  gauge: number;
  tube_radius: number;
}
/**
 * An open tray, such as a crop gutter: `width` across and `depth` deep,
 * its bottom's centre line from `start` to `end`. It may slope, as gutters
 * do to drain; it stays level across.
 */
export interface TrayPrimitive {
  fixture_id: string;
  material?: Material | null;
  obstructs?: Obstruction[] | null;
  primitive?: "tray";
  kind?: FixtureKind5;
  start: Vector3;
  end: Vector3;
  width: number;
  depth: number;
}
/**
 * A path on the floor, `width` wide, its centre line from `start` to
 * `end`.
 */
export interface WalkwayPrimitive {
  fixture_id: string;
  material?: Material | null;
  obstructs?: Obstruction[] | null;
  primitive?: "walkway";
  kind?: FixtureKind6;
  start: Point2;
  end: Point2;
  width: number;
}
/**
 * Each chosen piece of equipment, sensor, zone or fixture copied
 * `count` times, each copy `step` further than the one before.
 */
export interface RepeatItems {
  edit?: "repeat_items";
  items: string[];
  count: Count;
  step: Vector3;
}
/**
 * The chosen pieces of equipment, sensors, zones and fixtures spaced
 * evenly along an axis of the greenhouse.
 */
export interface SpaceItems {
  edit?: "space_items";
  items: string[];
  axis: Axis;
}
/**
 * On each chosen surface, doors or vents like `opening`, the first at
 * its centre and each next `step` further in the surface's plane.
 */
export interface PlaceOpenings {
  edit?: "place_openings";
  opening: Opening;
  surfaces: string[];
  count?: number;
  step?: Point2 | null;
}
/**
 * A door or vent: a rectangle on its host surface, centred at `centre` in
 * the host's own x-y plane, `width` along the host's x and `height` along
 * its y, open by `opening`, from 0 (closed) to 1.
 */
export interface Opening {
  /**
   * Letters, digits, '_', '.' and '-' only: the API's parameters write it between ':' and ','.
   */
  opening_id: string;
  kind: OpeningKind;
  surface_id: string;
  centre: Point2;
  width: number;
  height: number;
  opening?: number;
  largest_angle?: number;
}
/**
 * On each chosen surface, `count` doors or vents like `opening`, spread
 * evenly along it.
 */
export interface SpreadOpenings {
  edit?: "spread_openings";
  opening: Opening;
  surfaces: string[];
  count: Count;
}
/**
 * Each chosen door or vent copied `count` times on its surface, each
 * copy `step` further than the one before.
 */
export interface RepeatOpenings {
  edit?: "repeat_openings";
  openings: string[];
  count: Count;
  step: Point2;
}
/**
 * The chosen doors and vents of one surface spaced evenly along it.
 */
export interface SpaceOpenings {
  edit?: "space_openings";
  openings: string[];
}
/**
 * One field, a nested one by its path (`base.z`), given one value over
 * the chosen items: equipment, sensors, zones, fixtures, doors or
 * vents.
 */
export interface SetField {
  edit?: "set_field";
  items: string[];
  path: string;
  value: JsonValue;
}
/**
 * One field of the installation, by its path from the top
 * (`envelope.length`), given a value.
 */
export interface SetValue {
  edit?: "set_value";
  path: string;
  value: JsonValue;
}
/**
 * The chosen equipment, sensors, zones, fixtures, doors and vents
 * taken out.
 */
export interface RemoveItems {
  edit?: "remove_items";
  items: string[];
}
