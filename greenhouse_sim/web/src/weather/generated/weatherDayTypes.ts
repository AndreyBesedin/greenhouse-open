// Generated from greenhouse_sim/services/weather_day.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Bearing = number;

/**
 * A scenario's weather through its runs' first day: when the day
 * starts, and the weather every `every_s`, at those seconds from its
 * start, with where the sun stands and the direction towards it (P08.2),
 * for its path across the sky.
 */
export interface WeatherThroughADay {
  start: string;
  every_s: number;
  times_s: number[];
  weather: WeatherState[];
  sun: SunPosition[];
  sun_directions: Vector3[];
}
/**
 * The weather at a moment: the outside air's temperature, relative
 * humidity and CO2, the wind's speed and the direction it blows from, the
 * barometric pressure, the global radiation and the cloud cover.
 */
export interface WeatherState {
  air_temperature_c: number;
  relative_humidity_pct: number;
  co2_ppm: number;
  wind_speed_m_s: number;
  wind_direction_deg: Bearing | null;
  global_radiation_w_m2: number;
  cloud_cover_pct: number;
  barometric_pressure_hpa: number;
}
/**
 * Where the sun stands at a moment, seen from a site: its elevation
 * above the horizon (refraction included) and its azimuth, clockwise from
 * north, both in degrees; with its declination and the equation of time,
 * in minutes, for those who check them.
 */
export interface SunPosition {
  elevation_deg: number;
  azimuth_deg: number;
  declination_deg: number;
  equation_of_time_min: number;
}
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}
