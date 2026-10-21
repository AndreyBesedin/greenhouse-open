// Generated from greenhouse_sim/services/run_state.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Level = number;
/**
 * Where a point sensor stands, at a moment, with its readings.
 */
export type Freshness = "waiting" | "fresh" | "stale" | "unavailable";
export type Instant = string;
/**
 * What a MediaCapture recorded. The WUR canopy cameras (Oak-D S2 POE)
 * write an RGB image, a depth image aligned to it, and the left and right
 * infrared images the depth was computed from.
 */
export type CaptureModality = "RGB" | "DEPTH" | "INFRARED_LEFT" | "INFRARED_RIGHT";
export type SourceType = "SIMULATION" | "REAL_SENSORS" | "EXTERNAL_API" | "IMPORTED_DATA";

/**
 * What each process of a run holds at a moment.
 */
export interface RunState {
  run_id: string;
  start: string;
  time_s: number;
  day: number;
  at: string;
  house_air: HouseAirNow | null;
  crop_model: string;
  plants: number;
  days_lived: number;
  levels: {
    [k: string]: number;
  };
  commands_given: number;
  latest_commands: Command[];
  sensors: SensorFreshness[];
  cameras: CameraAt[];
}
/**
 * The house's air as one well-mixed volume at a moment.
 */
export interface HouseAirNow {
  temperature_c: number;
  humidity_pct: number;
  co2_ppm: number;
}
/**
 * Set one piece of equipment to a level, at a moment.
 */
export interface Command {
  time_s: number;
  actuator_id: string;
  level: Level;
}
/**
 * Whether a point sensor's latest reading due by a moment has come.
 */
export interface SensorFreshness {
  sensor_id: string;
  state: Freshness;
  due_at: string | null;
  latest_at: string | null;
}
/**
 * Where a camera stands with its frames at a moment of a run: how many
 * it has taken since the run's start, and its latest, if any.
 */
export interface CameraAt {
  sensor_id: string;
  frames: number;
  latest: CameraFrame | null;
}
/**
 * A frame a camera took: when, from where, turned how, with what
 * intrinsics, and what images it holds.
 */
export interface CameraFrame {
  frame_id: string;
  greenhouse_id: string;
  compartment_id: string | null;
  sensor_id: string;
  timestamp: Instant;
  pose: CameraPose;
  intrinsics: CameraIntrinsics;
  /**
   * @minItems 1
   */
  modalities: [CaptureModality, ...CaptureModality[]];
  source: RecordSource;
  delivered_at: Instant | null;
  capture_ids: string[];
}
/**
 * Where a camera stood, and how it was turned, in its greenhouse's
 * frame: x along the house, y across it and z up, in metres, from a corner
 * of its floor. The rotation, a unit quaternion (w, x, y, z), turns the
 * camera's own frame into the greenhouse's. In the camera's frame x runs
 * along the way it looks, y to its left and z up, so its picture's u runs
 * against y and its v against z. The optical convention, z along the way
 * it looks, x right and y down, is a fixed turn away.
 */
export interface CameraPose {
  x_m: number;
  y_m: number;
  z_m: number;
  qw: number;
  qx: number;
  qy: number;
  qz: number;
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
  distortion: number[];
}
/**
 * Where a piece of domain data came from - the system/run that
 * produced it (SIMULATION, REAL_SENSORS, ...) plus, where meaningful, the
 * id of that specific run/sensor/import (source_id) so the record stays
 * traceable without requiring the record itself to carry a simulation-
 * specific identity.
 */
export interface RecordSource {
  type: SourceType;
  source_id: string | null;
}
