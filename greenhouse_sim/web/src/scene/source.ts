import { PLANT_LAB_LAST_DAY, PLANT_LAB_SEED } from "../plants/lab";
import { stressPlants, stressScene } from "../qa/stressScene";
import { checkScene } from "./checkScene";
import type { SceneSnapshot } from "./generated/snapshotTypes";

/** Which scene the viewer draws, chosen in the address bar so a refresh keeps it. */
export type SceneSource =
  | { kind: "reference" }
  | { kind: "example" }
  /** One fixture of each primitive, side by side, as the simulator draws them. */
  | { kind: "fixtures" }
  /** The plant lab: a row of tomato plants from the organ-level model, on a
   * day of the lab's run, drawn from a seed. */
  | { kind: "plants"; day: number; seed: number }
  /** A dense field of plants built in the viewer, for measuring the renderer. */
  | { kind: "stress"; plants: number }
  /** A scenario's scene from the simulator, with another of its layouts if
   * `layout` names one, its greenhouse's dimensions changed as `envelope`
   * asks (length, width, spans, bays, eave_height, ridge_height), and its
   * doors and vents opened as `openings` asks (by opening identifier, from 0
   * to 1). */
  | {
      kind: "scenario";
      scenarioId: string;
      layout?: string;
      envelope?: Readonly<Record<string, number>>;
      openings?: Readonly<Record<string, number>>;
    }
  | { kind: "live"; scenarioId: string };

export type SceneState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "rejected"; problems: string[] }
  | { status: "loaded"; snapshot: SceneSnapshot };

const EXAMPLE_SCENE_URL = "/scenes/example.json";
// The simulator writes it (`tests/test_scene_schema.py --update`).
export const FIXTURE_GALLERY_URL = "/scenes/qa-fixtures.json";
export const PLANT_LAB_SCENE_URL = "/api/plants/scene";

export function sourceFromSearch(search: string): SceneSource {
  const parameters = new URLSearchParams(search);
  const liveId = parameters.get("live");
  if (liveId) {
    return { kind: "live", scenarioId: liveId };
  }
  const scenarioId = parameters.get("scenario");
  if (scenarioId) {
    const layout = parameters.get("layout");
    const envelope = pairsFrom(parameters.get("envelope"));
    const openings = pairsFrom(parameters.get("open"));
    return {
      kind: "scenario",
      scenarioId,
      ...(layout ? { layout } : {}),
      ...(envelope === null ? {} : { envelope }),
      ...(openings === null ? {} : { openings }),
    };
  }
  if (parameters.get("plants") === "lab") {
    return {
      kind: "plants",
      day: labDay(parameters.get("day")),
      seed: labSeed(parameters.get("seed")),
    };
  }
  switch (parameters.get("scene")) {
    case "example":
      return { kind: "example" };
    case "fixtures":
      return { kind: "fixtures" };
    case "stress":
      return { kind: "stress", plants: stressPlants(parameters.get("plants")) };
    default:
      return { kind: "reference" };
  }
}

/** The plant lab's day an address asks for: a whole number of days within
 * the lab's run, or its first day. */
function labDay(text: string | null): number {
  const day = Number(text ?? "0");
  return Number.isInteger(day) && day >= 0 && day <= PLANT_LAB_LAST_DAY ? day : 0;
}

/** The plant lab's seed an address asks for: a whole number from 0, or the
 * lab's own. */
function labSeed(text: string | null): number {
  const seed = Number(text ?? "");
  return text !== null && Number.isSafeInteger(seed) && seed >= 0 ? seed : PLANT_LAB_SEED;
}

/** The plant lab's day and seed as a query, leaving out what is as the lab
 * starts. */
function labQuery(source: { day: number; seed: number }, separator: "?" | "&"): string {
  const parts = [
    ...(source.day === 0 ? [] : [`day=${source.day}`]),
    ...(source.seed === PLANT_LAB_SEED ? [] : [`seed=${source.seed}`]),
  ];
  return parts.length === 0 ? "" : `${separator}${parts.join("&")}`;
}

export function searchFor(source: SceneSource): string {
  switch (source.kind) {
    case "reference":
      return "";
    case "example":
      return "?scene=example";
    case "fixtures":
      return "?scene=fixtures";
    case "plants":
      return `?plants=lab${labQuery(source, "&")}`;
    case "stress":
      return `?scene=stress&plants=${source.plants}`;
    case "scenario":
      return `?scenario=${encodeURIComponent(source.scenarioId)}${changesQuery(source, "&")}`;
    case "live":
      return `?live=${encodeURIComponent(source.scenarioId)}`;
  }
}

/** `key:number` pairs, sorted by key, as the address bar and the simulator's
 * API both take them: `length:12,spans:3`. */
function pairsText(pairs: Readonly<Record<string, number>> | undefined): string {
  return Object.entries(pairs ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, number]) => `${encodeURIComponent(key)}:${number}`)
    .join(",");
}

/** The changes a scenario's scene asks the simulator for: another of its
 * layouts (`layout=`), its greenhouse's dimensions (`envelope=`) and its
 * openings (`open=`), or nothing. */
function changesQuery(
  source: {
    layout?: string;
    envelope?: Readonly<Record<string, number>>;
    openings?: Readonly<Record<string, number>>;
  },
  separator: "?" | "&",
): string {
  const parts = [
    ["layout", encodeURIComponent(source.layout ?? "")],
    ["envelope", pairsText(source.envelope)],
    ["open", pairsText(source.openings)],
  ].filter(([, text]) => text !== "");
  return parts.length === 0
    ? ""
    : `${separator}${parts.map(([name, text]) => `${name}=${text}`).join("&")}`;
}

/** The pairs an address sets, or null when it sets none or says nothing
 * readable. The simulator checks the numbers themselves. */
function pairsFrom(value: string | null): Record<string, number> | null {
  if (!value) {
    return null;
  }
  const pairs: Record<string, number> = {};
  for (const pair of value.split(",")) {
    const [key, text] = pair.split(":");
    const number = Number(text);
    if (!key || text === undefined || Number.isNaN(number)) {
      return null;
    }
    pairs[key] = number;
  }
  return pairs;
}

function sceneUrl(source: SceneSource): string | null {
  switch (source.kind) {
    case "reference":
    case "stress":
    case "live":
      // A stress scene is built here, and a live scene streams in (see useLiveScene).
      return null;
    case "example":
      return EXAMPLE_SCENE_URL;
    case "fixtures":
      return FIXTURE_GALLERY_URL;
    case "plants":
      return `${PLANT_LAB_SCENE_URL}?day=${source.day}&seed=${source.seed}`;
    case "scenario":
      return `/api/scenarios/${encodeURIComponent(source.scenarioId)}/scene${changesQuery(source, "?")}`;
  }
}

/** Fetches and checks the chosen scene; every failure becomes a state to show. */
export async function loadScene(
  source: SceneSource,
  fetchFn: typeof fetch = fetch,
): Promise<SceneState> {
  if (source.kind === "stress") {
    // The viewer builds it, so it needs no check.
    return { status: "loaded", snapshot: stressScene(source.plants) };
  }
  const url = sceneUrl(source);
  return url === null ? { status: "none" } : fetchScene(url, fetchFn);
}

/** Why a scene was refused: the simulator's own reason, where it gives one. */
async function refusal(url: string, response: Response): Promise<string> {
  const answered = `${url} answered ${response.status}`;
  try {
    const body: unknown = await response.json();
    const error =
      typeof body === "object" && body !== null ? (body as Record<string, unknown>).error : null;
    return typeof error === "string" ? `${answered}: ${error}` : answered;
  } catch {
    return answered;
  }
}

/** Fetches and checks the scene at `url`; every failure becomes a state to show. */
export async function fetchScene(url: string, fetchFn: typeof fetch = fetch): Promise<SceneState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: await refusal(url, response) };
    }
    const check = checkScene(await response.json());
    return check.ok
      ? { status: "loaded", snapshot: check.snapshot }
      : { status: "rejected", problems: check.problems };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}
