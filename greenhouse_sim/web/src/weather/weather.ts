import { inWorld } from "../debug/dimensions";
import type { OverlayPrimitive } from "../debug/overlays";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { weatherParameter } from "../scene/source";
import type { Point3 } from "../world";

/** Where a scenario's world lies on the Earth: its latitude and longitude in
 * degrees, its elevation, its time zone, and the compass bearing its x axis
 * points to. */
export interface Site {
  latitude_deg: number;
  longitude_deg: number;
  elevation_m: number;
  time_zone: string;
  x_bearing_deg: number;
}

/** The weather outside at a moment, named as the protocol's outside
 * observation types are; the wind's direction is the one it blows from, in
 * degrees clockwise from north. */
export interface WeatherState {
  air_temperature_c: number;
  relative_humidity_pct: number;
  co2_ppm: number;
  wind_speed_m_s: number;
  /** Null when it is not known, as in a recording without a wind vane's. */
  wind_direction_deg: number | null;
  barometric_pressure_hpa: number;
  global_radiation_w_m2: number;
  cloud_cover_pct: number;
}

/** A scenario's weather at a moment of a run, as the simulator sends it
 * (`GET /api/scenarios/{id}/weather`): with the wind's velocity in the
 * world's axes. */
export interface WeatherAtAMoment {
  site: Site;
  /** The moment, as an instant. */
  moment: string;
  timeS: number;
  weather: WeatherState;
  windMS: Point3;
}

export type WeatherStateOfLoad =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; weather: WeatherAtAMoment };

/** A scenario's weather through its runs' first day, as the simulator sends
 * it (`GET /api/scenarios/{id}/weather/day`): when the day starts, and the
 * weather at seconds from then. */
export interface WeatherDay {
  start: string;
  timesS: number[];
  weather: WeatherState[];
}

export type WeatherDayState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; day: WeatherDay };

const SITE_NUMBERS = ["latitude_deg", "longitude_deg", "elevation_m", "x_bearing_deg"] as const;
const WEATHER_NUMBERS = [
  "air_temperature_c",
  "relative_humidity_pct",
  "co2_ppm",
  "wind_speed_m_s",
  "barometric_pressure_hpa",
  "global_radiation_w_m2",
  "cloud_cover_pct",
] as const;
// The sixteen points of the compass, from north clockwise.
const COMPASS_POINTS = [
  "N",
  "NNE",
  "NE",
  "ENE",
  "E",
  "ESE",
  "SE",
  "SSE",
  "S",
  "SSW",
  "SW",
  "WSW",
  "W",
  "WNW",
  "NW",
  "NNW",
] as const;
const DEGREES_IN_A_TURN = 360;
// The wind's arrow outside the house: a metre long for every metre a second,
// a metre clear of the house's corners, and drawn in the sky's blue.
const WIND_ARROW_M_PER_M_S = 1;
const WIND_ARROW_CLEARANCE_M = 1;
export const WIND_COLOR = "#2b7bb9";
const SPEED_DECIMALS = 1;

/** Where a scenario's weather at a moment of a run is published, under its
 * own weather or a preset's. */
export function weatherUrl(scenarioId: string, time: number, weather?: string): string {
  const parts = [...(time === 0 ? [] : [`t=${time}`]), ...weatherParameter(weather)];
  const query = parts.length === 0 ? "" : `?${parts.join("&")}`;
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/weather${query}`;
}

/** Where a scenario's weather through its runs' first day is published. */
export function weatherDayUrl(scenarioId: string, weather?: string): string {
  const query = weatherParameter(weather).join("&");
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/weather/day${query === "" ? "" : `?${query}`}`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isPoint(value: unknown): value is Point3 {
  return (
    isObject(value) &&
    typeof value.x === "number" &&
    typeof value.y === "number" &&
    typeof value.z === "number"
  );
}

function isWeatherState(value: unknown): value is WeatherState {
  return (
    isObject(value) &&
    WEATHER_NUMBERS.every((name) => typeof value[name] === "number") &&
    (typeof value.wind_direction_deg === "number" || value.wind_direction_deg === null)
  );
}

/** A day's weather, checked rather than trusted. */
export function parseWeatherDay(body: unknown): WeatherDay {
  if (
    !isObject(body) ||
    typeof body.start !== "string" ||
    !Array.isArray(body.times_s) ||
    !body.times_s.every((time) => typeof time === "number") ||
    !Array.isArray(body.weather) ||
    !body.weather.every(isWeatherState) ||
    body.weather.length !== body.times_s.length
  ) {
    throw new Error("the day's weather is not what the viewer expects");
  }
  return { start: body.start, timesS: body.times_s, weather: body.weather };
}

/** A weather response, checked rather than trusted. */
export function parseWeather(body: unknown): WeatherAtAMoment {
  if (
    !isObject(body) ||
    !isObject(body.site) ||
    typeof body.site.time_zone !== "string" ||
    !isObject(body.weather) ||
    typeof body.moment !== "string" ||
    typeof body.time_s !== "number" ||
    !isPoint(body.wind_m_s)
  ) {
    throw new Error("the weather is not what the viewer expects");
  }
  const site = body.site;
  const weather = body.weather;
  if (!SITE_NUMBERS.every((name) => typeof site[name] === "number") || !isWeatherState(weather)) {
    throw new Error("the weather is not what the viewer expects");
  }
  return {
    site: site as unknown as Site,
    moment: body.moment,
    timeS: body.time_s,
    weather,
    windMS: body.wind_m_s,
  };
}

/** Fetches a scenario's weather through its runs' first day; every failure
 * becomes `unavailable`. */
export async function loadWeatherDay(
  scenarioId: string,
  weather: string | undefined,
  fetchFn: typeof fetch = fetch,
): Promise<WeatherDayState> {
  try {
    const response = await fetchFn(weatherDayUrl(scenarioId, weather));
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", day: parseWeatherDay(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}

/** Fetches a scenario's weather at a moment of a run, under its own weather
 * or a preset's; every failure becomes `unavailable`. */
export async function loadWeather(
  scenarioId: string,
  time: number,
  weather: string | undefined,
  fetchFn: typeof fetch = fetch,
): Promise<WeatherStateOfLoad> {
  try {
    const response = await fetchFn(weatherUrl(scenarioId, time, weather));
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", weather: parseWeather(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}

/** The point of the compass nearest a bearing, such as "SW". */
export function compassPoint(bearingDeg: number): string {
  const share = DEGREES_IN_A_TURN / COMPASS_POINTS.length;
  const turned = ((bearingDeg % DEGREES_IN_A_TURN) + DEGREES_IN_A_TURN) % DEGREES_IN_A_TURN;
  return COMPASS_POINTS[Math.round(turned / share) % COMPASS_POINTS.length] ?? "N";
}

/** A wind, as the panel and the arrow write it: "4.0 m/s from the SW". */
export function describeWind(weather: WeatherState): string {
  if (weather.wind_speed_m_s === 0) {
    return "calm";
  }
  const speed = weather.wind_speed_m_s.toFixed(SPEED_DECIMALS);
  return weather.wind_direction_deg === null
    ? `${speed} m/s, its direction not known`
    : `${speed} m/s from the ${compassPoint(weather.wind_direction_deg)}`;
}

/**
 * The wind outside the house, in the world's axes: an arrow along it,
 * longer as it blows harder, ending a metre short of the house's corners
 * on the side it comes from, at half the house's height, labelled with the
 * wind. Nothing in a calm, or for a scene without the house's bounds.
 */
export function windOverlays(
  snapshot: SceneSnapshot,
  weather: WeatherAtAMoment,
): OverlayPrimitive[] {
  const bounds = snapshot.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS");
  const { x, y } = weather.windMS;
  const speed = Math.hypot(x, y);
  if (bounds?.shape.shape !== "box" || speed === 0) {
    return [];
  }
  const { size_x, size_y, size_z } = bounds.shape;
  const middle = inWorld(bounds.transform, { x: 0, y: 0, z: size_z / 2 });
  const along = { x: x / speed, y: y / speed, z: 0 };
  const length = WIND_ARROW_M_PER_M_S * speed;
  const back = Math.hypot(size_x, size_y) / 2 + WIND_ARROW_CLEARANCE_M + length;
  const origin = { x: middle.x - along.x * back, y: middle.y - along.y * back, z: middle.z };
  return [
    { id: "wind-arrow", kind: "arrow", origin, direction: along, length, color: WIND_COLOR },
    {
      id: "wind-label",
      kind: "label",
      position: origin,
      text: `wind ${describeWind(weather.weather)}`,
    },
  ];
}
