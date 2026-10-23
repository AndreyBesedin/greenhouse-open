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
export type Count = number;
export type Axis = "x" | "y" | "z";
export type OpeningKind = "door" | "roof_vent" | "side_vent";
export type JsonValue = unknown;

/**
 * Pieces of equipment or sensors like `item`, the first where it
 * stands and each next `step` further, named after its identifier.
 */
export interface PlaceItems {
  edit?: "place_items";
  item: Equipment | Sensor;
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
 * Each chosen piece of equipment or sensor copied `count` times, each
 * copy `step` further than the one before.
 */
export interface RepeatItems {
  edit?: "repeat_items";
  items: string[];
  count: Count;
  step: Vector3;
}
/**
 * The chosen pieces of equipment and sensors spaced evenly along an
 * axis of the greenhouse.
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
 * A point in a shape's own x-y plane.
 */
export interface Point2 {
  x: number;
  y: number;
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
 * the chosen items: equipment, sensors, doors or vents.
 */
export interface SetField {
  edit?: "set_field";
  items: string[];
  path: string;
  value: JsonValue;
}
/**
 * The chosen equipment, sensors, doors and vents taken out.
 */
export interface RemoveItems {
  edit?: "remove_items";
  items: string[];
}
