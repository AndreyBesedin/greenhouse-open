import { stressPlants, stressScene } from "../qa/stressScene";
import { checkScene } from "./checkScene";
import type { SceneSnapshot } from "./generated/snapshotTypes";

/** Which scene the viewer draws, chosen in the address bar so a refresh keeps it. */
export type SceneSource =
  | { kind: "reference" }
  | { kind: "example" }
  /** A dense field of plants built in the viewer, for measuring the renderer. */
  | { kind: "stress"; plants: number }
  | { kind: "scenario"; scenarioId: string }
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
    return { kind: "scenario", scenarioId };
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
      return `?scenario=${encodeURIComponent(source.scenarioId)}`;
    case "live":
      return `?live=${encodeURIComponent(source.scenarioId)}`;
  }
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
      return `/api/scenarios/${encodeURIComponent(source.scenarioId)}/scene`;
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
  if (url === null) {
    return { status: "none" };
  }
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `${url} answered ${response.status}` };
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
