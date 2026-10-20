// Generated from greenhouse_sim/services/observations.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Instant = string;
/**
 * What an Observation measures. The value doubles as the unit-bearing
 * field name on the reconstructed state models (EnvironmentState,
 * GreenhouseEnvironmentState), so a new greenhouse-level type is one enum
 * member plus one optional field, no mapping table.
 *
 * Plant-level readings come from a sensor or vision pass on one plant;
 * greenhouse-level readings (plant_id None) describe the compartment's
 * climate, its control state, or a manual sample across plants. Recorded
 * setpoints are observations of what the controller was asked to do, not
 * events: they are continuous 5-minute state, not discrete interventions.
 */
export type ObservationType =
  | "soil_moisture_pct"
  | "visible_fruit_count"
  | "ripe_fruit_count"
  | "estimated_ripe_mass_g"
  | "visible_height_cm"
  | "plant_height_cm"
  | "leaf_count"
  | "leaf_length_cm"
  | "leaf_width_cm"
  | "truss_count"
  | "open_flower_count"
  | "green_fruit_count"
  | "coloured_fruit_count"
  | "air_temperature_c"
  | "relative_humidity_pct"
  | "humidity_deficit_g_m3"
  | "co2_ppm"
  | "par_umol_m2_s"
  | "air_speed_m_s"
  | "heating_pipe_temperature_c"
  | "energy_screen_position_pct"
  | "blackout_screen_position_pct"
  | "window_position_lee_pct"
  | "window_position_wind_pct"
  | "lamps_activation_pct"
  | "heating_temperature_setpoint_c"
  | "ventilation_temperature_setpoint_c"
  | "co2_setpoint_ppm"
  | "humidity_deficit_setpoint_g_m3"
  | "lamps_activation_setpoint_pct"
  | "energy_screen_setpoint_pct"
  | "blackout_screen_setpoint_pct"
  | "irrigation_interval_setpoint_min"
  | "minimum_pipe_temperature_setpoint_c"
  | "minimum_window_position_lee_setpoint_pct"
  | "heating_temperature_effective_c"
  | "ventilation_temperature_lee_effective_c"
  | "ventilation_temperature_wind_effective_c"
  | "co2_effective_ppm"
  | "humidity_deficit_effective_g_m3"
  | "energy_screen_effective_pct"
  | "blackout_screen_effective_pct"
  | "irrigation_interval_effective_min"
  | "minimum_pipe_temperature_effective_c"
  | "minimum_window_position_lee_effective_pct"
  | "co2_dosing_on"
  | "co2_dosing_minutes_since_reset"
  | "heating_energy_increment_mj_m2"
  | "lighting_electricity_increment_kwh_m2"
  | "co2_dosed_increment_kg_m2"
  | "heating_cost_increment_eur_m2"
  | "lighting_cost_increment_eur_m2"
  | "co2_cost_increment_eur_m2"
  | "fixed_cost_increment_eur_m2"
  | "irrigation_flow_duration_min"
  | "drain_water_volume_l_m2"
  | "drain_ec_ds_m"
  | "drain_ph"
  | "sampled_fruit_count_per_plant"
  | "sampled_fruit_fresh_weight_g_per_plant"
  | "plant_density_per_m2"
  | "outside_air_temperature_c"
  | "outside_relative_humidity_pct"
  | "outside_humidity_deficit_g_m3"
  | "outside_absolute_humidity_g_m3"
  | "outside_global_radiation_w_m2"
  | "outside_radiation_sum_j_cm2"
  | "outside_wind_speed_m_s"
  | "outside_wind_direction_deg"
  | "outside_barometric_pressure_hpa"
  | "outside_cloud_cover_pct"
  | "outside_rain"
  | "outside_par_umol_m2_s"
  | "outside_heat_emission_w_m2"
  | "outside_co2_ppm"
  | "forecast_radiation_sum_today_j_cm2";
export type SourceType = "SIMULATION" | "REAL_SENSORS" | "EXTERNAL_API" | "IMPORTED_DATA";
/**
 * Where a point sensor stands, at a moment, with its readings.
 */
export type Freshness = "waiting" | "fresh" | "stale" | "unavailable";
/**
 * What a MediaCapture recorded. The WUR canopy cameras (Oak-D S2 POE)
 * write an RGB image, a depth image aligned to it, and the left and right
 * infrared images the depth was computed from.
 */
export type CaptureModality = "RGB" | "DEPTH" | "INFRARED_LEFT" | "INFRARED_RIGHT";

/**
 * A run's observation log up to a moment: what its point sensors
 * observed, in the order delivered, whether each is fresh, and the frames
 * its cameras took; the run that produced them, and when it started.
 */
export interface SensorObservations {
  run_id: string;
  start: string;
  observations: Observation[];
  freshness: SensorFreshness[];
  frames: CameraFrame[];
}
export interface Observation {
  observation_id: string;
  greenhouse_id: string;
  compartment_id: string | null;
  plant_id: string | null;
  timestamp: Instant;
  observation_type: ObservationType;
  value: number;
  source: RecordSource;
  sensor_id?: string | null;
  delivered_at?: Instant | null;
  quality?: string[];
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
