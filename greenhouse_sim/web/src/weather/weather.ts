import { dayEnd, runDay } from "../clock";
import { inWorld } from "../debug/dimensions";
import type { OverlayPrimitive } from "../debug/overlays";
import { contractReader, loadJson } from "../loadJson";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { runParameters, scenarioUrl } from "../scene/run";
import { PERCENT } from "../units";
import type { Point3 } from "../world";
import { WEATHER_DAY_SCHEMA } from "./generated/weatherDaySchema";
import type { WeatherThroughADay } from "./generated/weatherDayTypes";
import { WEATHER_SCHEMA } from "./generated/weatherSchema";
import type {
  OutsideLight,
  WeatherAtAMoment as ServedWeather,
  Site,
  WeatherState,
} from "./generated/weatherTypes";

// Where a scenario's world lies on the Earth, the weather outside at a
// moment, and the sun's and the sky's light then, as the simulator publishes
// them; the wind's direction is the one it blows from.
export type { OutsideLight, Site, WeatherState };

/** Where the sun stands at a moment: its elevation above the horizon and its
 * azimuth, clockwise from north, in degrees. */
export interface SunPosition {
  elevation_deg: number;
  azimuth_deg: number;
}

/** A scenario's weather at a moment of a run, as the simulator sends it
 * (`GET /api/scenarios/{id}/weather`): with the wind's velocity in the
 * world's axes, where the sun stands, with the direction towards it, and
 * its light and the sky's. */
export interface WeatherAtAMoment {
  site: Site;
  /** The moment, as an instant. */
  moment: string;
  timeS: number;
  weather: WeatherState;
  windMS: Point3;
  sun: SunPosition;
  sunDirection: Point3;
  light: OutsideLight;
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
  /** Where the sun stands at each moment, and the direction towards it. */
  sun: SunPosition[];
  sunDirections: Point3[];
}

export type WeatherDayState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; day: WeatherDay };

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
  return scenarioUrl(scenarioId, "weather", runParameters({ time, weather }, ["time", "weather"]));
}

/** Where a scenario's weather through the day of a moment of a run is
 * published. A day is asked for by its last moment (`../clock`), so that
 * every moment of it asks the same; the first, by none. */
export function weatherDayUrl(scenarioId: string, time: number, weather?: string): string {
  const asked = runDay(time) === 0 ? undefined : dayEnd(time);
  return scenarioUrl(
    scenarioId,
    "weather/day",
    runParameters({ time: asked, weather }, ["time", "weather"]),
  );
}

const readWeatherDay = contractReader<WeatherThroughADay>(
  WEATHER_DAY_SCHEMA,
  "the day's weather is not what the viewer expects",
);
const readWeather = contractReader<ServedWeather>(
  WEATHER_SCHEMA,
  "the weather is not what the viewer expects",
);

/** Where the sun stands, without what the viewer does not show of it. */
function sunOf({ elevation_deg, azimuth_deg }: SunPosition): SunPosition {
  return { elevation_deg, azimuth_deg };
}

/** A day's weather, checked rather than trusted: at each of its moments, the
 * weather and the sun. */
export function parseWeatherDay(body: unknown): WeatherDay {
  const day = readWeatherDay(body);
  const moments = day.times_s.length;
  if (
    day.weather.length !== moments ||
    day.sun.length !== moments ||
    day.sun_directions.length !== moments
  ) {
    throw new Error("the day's weather is not what the viewer expects");
  }
  return {
    start: day.start,
    timesS: day.times_s,
    weather: day.weather,
    sun: day.sun.map(sunOf),
    sunDirections: day.sun_directions,
  };
}

/** A weather response, checked rather than trusted. */
export function parseWeather(body: unknown): WeatherAtAMoment {
  const served = readWeather(body);
  return {
    site: served.site,
    moment: served.moment,
    timeS: served.time_s,
    weather: served.weather,
    windMS: served.wind_m_s,
    sun: sunOf(served.sun),
    sunDirection: served.sun_direction,
    light: served.light,
  };
}

/** Fetches a scenario's weather through its runs' first day, from its
 * `weatherDayUrl`; every failure becomes `unavailable`. */
export async function loadWeatherDay(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<WeatherDayState> {
  const answer = await loadJson(url, parseWeatherDay, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", day: answer.value } : answer;
}

/** Fetches a scenario's weather at a moment of a run, under its own weather
 * or a preset's, from its `weatherUrl`; every failure becomes `unavailable`. */
export async function loadWeather(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<WeatherStateOfLoad> {
  const answer = await loadJson(url, parseWeather, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", weather: answer.value } : answer;
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

// The sun's marker stands this many times the house's longer side from its
// middle, in the sun's direction, so that it is in the sky of any view.
const SUN_REACH = 1.5;
// Its arrow, a short pointer along its light: the scene's light and
// shadows show the rest of the way.
const SUN_ARROW_LENGTH_M = 2;
export const SUN_COLOR = "#e6a800";

/** Where the sun stands, in words: "14.6° up, at 180° (S)". */
export function describeSun(sun: SunPosition): string {
  if (sun.elevation_deg <= 0) {
    return "below the horizon";
  }
  return `${sun.elevation_deg.toFixed(SPEED_DECIMALS)}° up, at ${Math.round(sun.azimuth_deg)}° (${compassPoint(sun.azimuth_deg)})`;
}

/** The light outside, in words: "572 W/m², 28% of it the sky's, PAR 1229
 * µmol/m²/s", or "dark". */
export function describeLight(light: OutsideLight): string {
  if (light.ghi_w_m2 <= 0) {
    return "dark";
  }
  const sky = Math.round((light.dhi_w_m2 / light.ghi_w_m2) * PERCENT);
  return `${Math.round(light.ghi_w_m2)} W/m², ${sky}% of it the sky's, PAR ${Math.round(light.par_umol_m2_s)} µmol/m²/s`;
}

/**
 * The sun in the scene, while it is up: a marker in the sky in its
 * direction from the house's middle, a short arrow from it towards the
 * house, along its light, and a label. Nothing at night, or for a scene without the
 * house's bounds.
 */
export function sunOverlays(
  snapshot: SceneSnapshot,
  weather: WeatherAtAMoment,
): OverlayPrimitive[] {
  const bounds = snapshot.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS");
  if (bounds?.shape.shape !== "box" || weather.sun.elevation_deg <= 0) {
    return [];
  }
  const { size_x, size_y, size_z } = bounds.shape;
  const middle = inWorld(bounds.transform, { x: 0, y: 0, z: size_z / 2 });
  const reach = Math.max(size_x, size_y) * SUN_REACH;
  const towards = weather.sunDirection;
  const marker = {
    x: middle.x + towards.x * reach,
    y: middle.y + towards.y * reach,
    z: middle.z + towards.z * reach,
  };
  const along = { x: -towards.x, y: -towards.y, z: -towards.z };
  return [
    { id: "sun-marker", kind: "point", position: marker, color: SUN_COLOR },
    {
      id: "sun-arrow",
      kind: "arrow",
      origin: marker,
      direction: along,
      length: SUN_ARROW_LENGTH_M,
      color: SUN_COLOR,
    },
    { id: "sun-label", kind: "label", position: marker, text: `sun ${describeSun(weather.sun)}` },
  ];
}
