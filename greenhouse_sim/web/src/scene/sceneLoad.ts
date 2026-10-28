/**
 * A scene loaded for the viewer to draw (`SceneSource`'s): an example's or
 * the fixture gallery's file, the plant lab's or a scenario's scene from the
 * simulator, its equipment, doors and vents as they stand at the moment of
 * its climate run drawn, or a stress scene the viewer builds itself.
 */
import { loadJson } from "../loadJson";
import { labRunQuery } from "../plants/lab";
import { stressScene } from "../qa/stressScene";
import { checkScene } from "./checkScene";
import { standingAt } from "./edits";
import type { SceneSnapshot } from "./generated/snapshotTypes";
import { changesQuery, type SceneSource } from "./source";

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
function sceneUrl(
  source: SceneSource,
  openingIds: readonly string[] = [],
  governed: Readonly<Record<string, number>> = {},
): string | null {
  switch (source.kind) {
    case "reference":
    case "stress":
      // A stress scene is built here.
      return null;
    case "example":
      return EXAMPLE_SCENE_URL;
    case "fixtures":
      return FIXTURE_GALLERY_URL;
    case "plants":
      return `${PLANT_LAB_SCENE_URL}?${labRunQuery(source)}`;
    case "scenario":
      // Its equipment, and its doors and vents, as they stand at the moment of
      // its climate run drawn, its thermostat's heater as the run has it.
      return `/api/scenarios/${encodeURIComponent(source.scenarioId)}/scene${changesQuery(standingAt(source, openingIds, governed), "?")}`;
  }
}

/** What a scene is asked for by: its address, or, for a stress scene, which
 * the viewer builds itself, its size; null for none. */
export function sceneRequest(
  source: SceneSource,
  openingIds: readonly string[] = [],
  governed: Readonly<Record<string, number>> = {},
): string | null {
  return source.kind === "stress"
    ? `stress ${source.plants}`
    : sceneUrl(source, openingIds, governed);
}

/** Fetches and checks the chosen scene; every failure becomes a state to show. */
export async function loadScene(
  source: SceneSource,
  fetchFn: typeof fetch = fetch,
  openingIds: readonly string[] = [],
  governed: Readonly<Record<string, number>> = {},
): Promise<SceneState> {
  if (source.kind === "stress") {
    // The viewer builds it, so it needs no check.
    return { status: "loaded", snapshot: stressScene(source.plants) };
  }
  const url = sceneUrl(source, openingIds, governed);
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
  const answer = await loadJson(url, checkScene, fetchFn, (response) => refusal(url, response));
  if (answer.status !== "loaded") {
    return answer;
  }
  const check = answer.value;
  return check.ok
    ? { status: "loaded", snapshot: check.snapshot }
    : { status: "rejected", problems: check.problems };
}
