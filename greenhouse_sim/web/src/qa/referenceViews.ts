import type { CameraPose } from "../camera";
import type { ScalarRange } from "../debug/scalar";
import type { Slice, SliceQuantity } from "../fields/display";
import { quantityScale } from "../fields/drawing";
import { checkField, type EnvironmentField } from "../fields/field";
import { type OpeningsAt, parseOpenings } from "../fields/openingFlows";
import { isNumberRecord, isObject } from "../loadJson";
import { formatValue } from "../readouts";
import { checkScene } from "../scene/checkScene";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import {
  parseWeather,
  parseWeatherDay,
  type WeatherAtAMoment,
  type WeatherDay,
} from "../weather/weather";
import { QA_REFERENCE_VIEWS, type QaReferenceView } from "./referencePage";

export { QA_REFERENCE_PATH, QA_REFERENCE_VIEWS, type QaReferenceView } from "./referencePage";

// P09's golden views: the reference run at moments of its opening day and of
// a young crop's, as the simulator writes them, gzipped
// (`tests/test_reference_qa.py --update`), drawn from fixed views.
export const QA_REFERENCE_URL = "/scenes/qa-reference-greenhouse.json.gz";

// The moments the file holds: the opening day's dawn, sun's noon and
// evening, its noon with the fans turned off or the vents shut an hour
// before, and a young crop's noon.
const MOMENTS = ["dawn", "noon", "evening", "fans-off", "vents-shut", "young"] as const;
export type ReferenceMomentName = (typeof MOMENTS)[number];

/** What one moment's views draw: the house then, without its crop, the
 * crop's day, the weather, the climate field's channels its views draw and
 * what its vents pass, where they draw them, and its state probes. */
export interface ReferenceMoment {
  timeS: number;
  house: SceneSnapshot;
  cropDay: number;
  weather: WeatherAtAMoment;
  field: EnvironmentField | null;
  openings: OpeningsAt | null;
  probes: Record<string, number>;
}

/** The reference QA file: its moments, the crop on each day drawn, and the
 * sun's path through the opening day. */
export interface ReferenceQa {
  moments: Record<ReferenceMomentName, ReferenceMoment>;
  crops: Record<string, SceneSnapshot>;
  sunPath: WeatherDay;
}

/** How a view draws its moment: lit by the sun with its path; with its air
 * as arrows; with a slice through it; as the path camera's picture or its
 * depth; or the scene alone, for its crop. */
export type ReferenceLayer =
  | { kind: "sun" }
  | { kind: "arrows" }
  | { kind: "slice"; slice: Slice }
  | { kind: "camera"; pass: "rgb" | "depth" }
  | { kind: "scene" };

export interface ReferenceView {
  moment: ReferenceMomentName;
  layer: ReferenceLayer;
  pose: CameraPose;
  /** The moments whose fields share this view's colours, so that the pair
   * it is compared with is drawn on one scale. */
  sharing?: readonly ReferenceMomentName[];
}

// The house is 12 m long along x and 9.6 m wide; its fans blow down it from
// 3 m up over the front path, from y 3.2 and 6.4; its rows run from x 3 to
// 8.25 at y 2.4, 4.0, 5.6 and 7.2, and its roof vents lie along the middle.
const MIDDLE = { x: 6, y: 4.8 };
// From outside, south-west of the house and above it, as the solar QA is
// seen: its shadows on the floor in view.
const OUTSIDE: CameraPose = {
  position: { x: -7, y: -9, z: 11 },
  target: { x: MIDDLE.x, y: MIDDLE.y, z: 0.5 },
};
// From beside the house, level with the fans, along their jets.
const BESIDE_THE_JETS: CameraPose = {
  position: { x: 5, y: -9, z: 6 },
  target: { x: 5, y: MIDDLE.y, z: 2.5 },
};
// Along the house from in front of it and above its door, at the slice
// across its middle.
const ACROSS_THE_HOUSE: CameraPose = {
  position: { x: -7, y: MIDDLE.y, z: 8 },
  target: { x: MIDDLE.x, y: MIDDLE.y, z: 2 },
};
// Inside, from the right side's path, at the first row's middle.
const BESIDE_A_ROW: CameraPose = {
  position: { x: 4, y: 0.4, z: 2.2 },
  target: { x: 6, y: 2.4, z: 1.6 },
};
// From straight above, leaning a millimetre so that "up" on screen is
// defined.
const ABOVE_M = 16;
const LEAN_M = 0.001;
const ABOVE: CameraPose = {
  position: { x: MIDDLE.x, y: MIDDLE.y - LEAN_M, z: ABOVE_M },
  target: { x: MIDDLE.x, y: MIDDLE.y, z: 0 },
};
const FANS: readonly ReferenceMomentName[] = ["noon", "fans-off"];
const VENTS: readonly ReferenceMomentName[] = ["noon", "vents-shut"];
// The vents' effect, across the house's middle, from the floor to the roof.
const ACROSS: Slice = { quantity: "temperature", axis: "x", position: MIDDLE.x };
// The right fan's jet, along the house.
const ALONG_THE_JET: Slice = { quantity: "speed", axis: "y", position: 3.2 };
// The light at the crop's middle height.
const IN_THE_CANOPY: Slice = { quantity: "par", axis: "z", position: 1.75 };

export const REFERENCE_VIEWS: Record<QaReferenceView, ReferenceView> = {
  dawn: { moment: "dawn", layer: { kind: "sun" }, pose: OUTSIDE },
  noon: { moment: "noon", layer: { kind: "sun" }, pose: OUTSIDE },
  evening: { moment: "evening", layer: { kind: "sun" }, pose: OUTSIDE },
  "fans-on": { moment: "noon", layer: { kind: "arrows" }, pose: BESIDE_THE_JETS, sharing: FANS },
  "fans-off": {
    moment: "fans-off",
    layer: { kind: "arrows" },
    pose: BESIDE_THE_JETS,
    sharing: FANS,
  },
  "vents-open": {
    moment: "noon",
    layer: { kind: "slice", slice: ACROSS },
    pose: ACROSS_THE_HOUSE,
    sharing: VENTS,
  },
  "vents-closed": {
    moment: "vents-shut",
    layer: { kind: "slice", slice: ACROSS },
    pose: ACROSS_THE_HOUSE,
    sharing: VENTS,
  },
  young: { moment: "young", layer: { kind: "scene" }, pose: BESIDE_A_ROW },
  fruiting: { moment: "noon", layer: { kind: "scene" }, pose: BESIDE_A_ROW },
  "camera-rgb": { moment: "noon", layer: { kind: "camera", pass: "rgb" }, pose: OUTSIDE },
  "camera-depth": { moment: "noon", layer: { kind: "camera", pass: "depth" }, pose: OUTSIDE },
  "airflow-slice": {
    moment: "noon",
    layer: { kind: "slice", slice: ALONG_THE_JET },
    pose: BESIDE_THE_JETS,
  },
  "radiation-slice": {
    moment: "noon",
    layer: { kind: "slice", slice: IN_THE_CANOPY },
    pose: ABOVE,
  },
};

/** The view a QA address asks for, or the noon's by default; null for a
 * view there is not. */
export function qaReferenceView(search: string): QaReferenceView | null {
  const view = new URLSearchParams(search).get("view") ?? "noon";
  return (QA_REFERENCE_VIEWS as readonly string[]).includes(view)
    ? (view as QaReferenceView)
    : null;
}

function scene(body: unknown, what: string): SceneSnapshot {
  const check = checkScene(body);
  if (!check.ok) {
    throw new Error(`the reference QA's ${what}: ${check.problems.join("; ")}`);
  }
  return check.snapshot;
}

function probesFrom(body: unknown, what: string): Record<string, number> {
  if (!isNumberRecord(body)) {
    throw new Error(`the reference QA's ${what} has no probes`);
  }
  return body;
}

function momentFrom(body: unknown, name: string): ReferenceMoment {
  if (!isObject(body) || typeof body.time_s !== "number" || typeof body.crop_day !== "number") {
    throw new Error(`the reference QA has no ${name}`);
  }
  let field: EnvironmentField | null = null;
  if (body.field !== undefined) {
    const check = checkField(body.field);
    if (!check.ok) {
      throw new Error(`the reference QA's ${name} field: ${check.problems.join("; ")}`);
    }
    field = check.field;
  }
  return {
    timeS: body.time_s,
    house: scene(body.house, `${name} house`),
    cropDay: body.crop_day,
    weather: parseWeather(body.weather),
    field,
    openings: body.openings === undefined ? null : parseOpenings(body.openings),
    probes: probesFrom(body.probes, name),
  };
}

/** The reference QA file, checked rather than trusted. */
export function parseReferenceQa(body: unknown): ReferenceQa {
  if (!isObject(body) || !isObject(body.moments) || !isObject(body.crops)) {
    throw new Error("the reference QA is not what the viewer expects");
  }
  const { moments, crops } = body;
  const parsed: Partial<ReferenceQa["moments"]> = {};
  for (const name of MOMENTS) {
    parsed[name] = momentFrom(moments[name], name);
  }
  const keptCrops: Record<string, SceneSnapshot> = {};
  for (const [day, crop] of Object.entries(crops)) {
    keptCrops[day] = scene(crop, `day ${day} crop`);
  }
  for (const moment of Object.values(parsed)) {
    if (keptCrops[String(moment.cropDay)] === undefined) {
      throw new Error(`the reference QA has no crop on day ${moment.cropDay}`);
    }
  }
  return {
    moments: parsed as ReferenceQa["moments"],
    crops: keptCrops,
    sunPath: parseWeatherDay(body.sun_path),
  };
}

// A gzipped file's first two bytes.
const GZIP_FIRST = 0x1f;
const GZIP_SECOND = 0x8b;

/** JSON from a gzipped file, unzipped here unless the server already has. */
export async function gzippedJson(response: Response): Promise<unknown> {
  const bytes = new Uint8Array(await response.arrayBuffer());
  const zipped = bytes[0] === GZIP_FIRST && bytes[1] === GZIP_SECOND;
  const text = zipped
    ? await new Response(
        new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip")),
      ).text()
    : new TextDecoder().decode(bytes);
  return JSON.parse(text);
}

export type ReferenceQaState =
  | { status: "loading" }
  | { status: "missing"; reason: string }
  | { status: "loaded"; qa: ReferenceQa };

/** Fetches the reference QA file; a failure is the reason it is missing. */
export async function loadReferenceQa(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<ReferenceQaState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      throw new Error(`the file answered ${response.status}`);
    }
    return { status: "loaded", qa: parseReferenceQa(await gzippedJson(response)) };
  } catch (error) {
    return { status: "missing", reason: error instanceof Error ? error.message : String(error) };
  }
}

/** The scale a view's field is drawn on: the quantity its layer draws, over
 * the widest range the moments it shares its colours with reach. */
export function referenceScale(
  qa: ReferenceQa,
  view: ReferenceView,
): { quantity: SliceQuantity; title: string; unit: string; range: ScalarRange } | null {
  const quantity =
    view.layer.kind === "arrows"
      ? "speed"
      : view.layer.kind === "slice"
        ? view.layer.slice.quantity
        : null;
  const field = qa.moments[view.moment].field;
  if (quantity === null || field === null) {
    return null;
  }
  const own = quantityScale(field, quantity);
  if (own === null) {
    return null;
  }
  const ranges = (view.sharing ?? [view.moment]).flatMap((name) => {
    const shared = qa.moments[name].field;
    const scale = shared === null ? null : quantityScale(shared, quantity);
    return scale === null ? [] : [scale.range];
  });
  return {
    quantity,
    title: own.title,
    unit: own.unit,
    range: {
      min: Math.min(...ranges.map((range) => range.min)),
      max: Math.max(...ranges.map((range) => range.max)),
    },
  };
}

// How each probe is said, in the order said.
const PROBE_WORDS: readonly [string, (value: number) => string][] = [
  ["house_air_c", (value) => `house air ${formatValue(value)} °C`],
  ["sun_elevation_deg", (value) => `sun ${formatValue(value)}° up`],
  ["jet_m_s", (value) => `jet ${formatValue(value)} m/s`],
  ["vents_exchange_m3_s", (value) => `vents exchange ${formatValue(value)} m³/s`],
  ["leaves", (value) => `${value} leaves`],
  ["fruits", (value) => `${value} fruits`],
  ["red_fruits", (value) => `${value} red`],
];

/** A moment's state probes in words: "house air 29.46 °C, sun 58.05° up, …". */
export function describeProbes(probes: Record<string, number>): string {
  return PROBE_WORDS.flatMap(([name, say]) => {
    const value = probes[name];
    return value === undefined ? [] : [say(value)];
  }).join(", ");
}
