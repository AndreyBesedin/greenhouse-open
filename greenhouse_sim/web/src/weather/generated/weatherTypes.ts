// Generated from greenhouse_sim/services/weather.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Bearing = number;

/**
 * The weather at a moment of a scenario's run: its site, the moment, as
 * an instant and in seconds from the run's start, the weather then, the
 * wind's velocity in the world's axes, where the sun stands, with the
 * direction towards it in the world's axes (P08.1), and its light and the
 * sky's (P08.3).
 */
export interface WeatherAtAMoment {
  site: Site;
  moment: string;
  time_s: number;
  weather: WeatherState;
  wind_m_s: Vector3;
  sun: SunPosition;
  sun_direction: Vector3;
  light: OutsideLight;
}
/**
 * Where the world lies: its latitude and longitude (degrees north and
 * east), its elevation (metres above sea level), its time zone (by its
 * IANA name, such as `Europe/Amsterdam`), and the bearing of its x axis.
 */
export interface Site {
  latitude_deg: number;
  longitude_deg: number;
  elevation_m: number;
  time_zone: string;
  x_bearing_deg: number;
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
export interface Vector3 {
  x: number;
  y: number;
  z: number;
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
/**
 * The light outside at a moment: its global horizontal irradiance, its
 * beam's direct normal irradiance and the diffuse sky's on a level
 * surface, in W/m², and its PAR on a level surface, in µmol/m²/s.
 */
export interface OutsideLight {
  ghi_w_m2: number;
  dni_w_m2: number;
  dhi_w_m2: number;
  par_umol_m2_s: number;
}
