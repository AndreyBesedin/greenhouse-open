import { stressPlants, stressScene } from "../qa/stressScene";
import { checkScene } from "./checkScene";
import type { SceneSnapshot } from "./generated/snapshotTypes";

/** Which scene the viewer draws, chosen in the address bar so a refresh keeps it. */
export type SceneSource =
  | { kind: "reference" }
  | { kind: "example" }
  /** A dense field of plants built in the viewer, for measuring the renderer. */
  | { kind: "stress"; plants: number }
  /** A scenario's scene from the simulator, its greenhouse's dimensions
   * changed as `envelope` asks (length, width, spans, bays, eave_height,
   * ridge_height), and its doors and vents opened as `openings` asks (by
   * opening identifier, from 0 to 1). */
  | {
      kind: "scenario";
      scenarioId: string;
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

export function sourceFromSearch(search: string): SceneSource {
  const parameters = new URLSearchParams(search);
  const liveId = parameters.get("live");
  if (liveId) {
    return { kind: "live", scenarioId: liveId };
  }
  const scenarioId = parameters.get("scenario");
  if (scenarioId) {
    const envelope = pairsFrom(parameters.get("envelope"));
    const openings = pairsFrom(parameters.get("open"));
    return {
      kind: "scenario",
      scenarioId,
      ...(envelope === null ? {} : { envelope }),
      ...(openings === null ? {} : { openings }),
    };
  }
  switch (parameters.get("scene")) {
    case "example":
      return { kind: "example" };
    case "stress":
      return { kind: "stress", plants: stressPlants(parameters.get("plants")) };
    default:
      return { kind: "reference" };
  }
}

export function searchFor(source: SceneSource): string {
  switch (source.kind) {
    case "reference":
      return "";
    case "example":
      return "?scene=example";
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

/** The changes a scenario's scene asks the simulator for: its greenhouse's
 * dimensions (`envelope=`) and its openings (`open=`), or nothing. */
function changesQuery(
  source: {
    envelope?: Readonly<Record<string, number>>;
    openings?: Readonly<Record<string, number>>;
  },
  separator: "?" | "&",
): string {
  const parts = [
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
