import type { CameraPose } from "../camera";
import type { ScalarRange } from "../debug/scalar";
import type { Slice } from "../fields/display";
import { checkField, type EnvironmentField } from "../fields/field";
import {
  parseWeather,
  parseWeatherDay,
  type WeatherAtAMoment,
  type WeatherDay,
} from "../weather/weather";

// P08's equinox views: the solar lab's scene, and its light at three moments
// of its clear equinox day, as the simulator writes them
// (`tests/test_solar_qa.py --update`), drawn from one fixed view.
export const QA_SOLAR_PATH = "/qa/solar-lab";
export const QA_SOLAR_SCENE_URL = "/scenes/qa-solar-lab.json";
export const QA_SOLAR_LIGHT_URL = "/fields/qa-solar-lab-light.json";
export const QA_SOLAR_VIEWS = ["morning", "noon", "evening"] as const;
export type QaSolarView = (typeof QA_SOLAR_VIEWS)[number];

// The house is 12 m long and 6.4 m wide. It is seen from the south-west and
// above, looking at the middle of its floor, so that the shadows the crates
// and the row of plants cast north and east of them lie in view.
const MIDDLE = { x: 6, y: 3.2 };
export const QA_SOLAR_POSE: CameraPose = {
  position: { x: -2, y: -7, z: 9 },
  target: { x: MIDDLE.x, y: MIDDLE.y, z: 0.5 },
};
// The PAR on the floor's cells' level, a quarter of a metre up.
export const QA_SOLAR_SLICE: Slice = { quantity: "par", axis: "z", position: 0.25 };

/** The view a QA address asks for, or the noon's by default; null for a
 * view there is not. */
export function qaSolarView(search: string): QaSolarView | null {
  const view = new URLSearchParams(search).get("view") ?? "noon";
  return (QA_SOLAR_VIEWS as readonly string[]).includes(view) ? (view as QaSolarView) : null;
}

/** The solar lab's light at each moment drawn, and the sun's path through
 * its day. */
export interface SolarLight {
  views: Record<QaSolarView, { weather: WeatherAtAMoment; field: EnvironmentField }>;
  day: WeatherDay;
}

/** The solar QA's light file, checked rather than trusted. */
export function parseSolarLight(body: unknown): SolarLight {
  if (typeof body !== "object" || body === null || !("views" in body) || !("day" in body)) {
    throw new Error("the solar QA's light is not what the viewer expects");
  }
  const { views, day } = body as {
    views: Record<string, { weather: unknown; field: unknown }>;
    day: unknown;
  };
  const parsed: Partial<SolarLight["views"]> = {};
  for (const view of QA_SOLAR_VIEWS) {
    const entry = views[view];
    if (entry === undefined) {
      throw new Error(`the solar QA's light has no ${view}`);
    }
    const check = checkField(entry.field);
    if (!check.ok) {
      throw new Error(`the solar QA's ${view} field: ${check.problems.join("; ")}`);
    }
    parsed[view] = { weather: parseWeather(entry.weather), field: check.field };
  }
  return { views: parsed as SolarLight["views"], day: parseWeatherDay(day) };
}

/** The PAR colours run over the same range in every view: from nothing to
 * the most any of them has, so that the morning's light looks dimmer than
 * the noon's. */
export function solarRange(light: SolarLight): ScalarRange {
  const most = Math.max(
    ...QA_SOLAR_VIEWS.map((view) => light.views[view].field.channels.par?.maximum ?? 0),
  );
  return { min: 0, max: most };
}
