import { checkScene } from "./checkScene";
import type { SceneSnapshot } from "./generated/snapshotTypes";

/** Which scene the viewer draws, chosen in the address bar so a refresh keeps it. */
export type SceneSource =
  | { kind: "reference" }
  | { kind: "example" }
  | { kind: "scenario"; scenarioId: string };

export type SceneState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "rejected"; problems: string[] }
  | { status: "loaded"; snapshot: SceneSnapshot };

const EXAMPLE_SCENE_URL = "/scenes/example.json";

export function sourceFromSearch(search: string): SceneSource {
  const parameters = new URLSearchParams(search);
  const scenarioId = parameters.get("scenario");
  if (scenarioId) {
    return { kind: "scenario", scenarioId };
  }
  return parameters.get("scene") === "example" ? { kind: "example" } : { kind: "reference" };
}

export function searchFor(source: SceneSource): string {
  switch (source.kind) {
    case "reference":
      return "";
    case "example":
      return "?scene=example";
    case "scenario":
      return `?scenario=${encodeURIComponent(source.scenarioId)}`;
  }
}

function sceneUrl(source: SceneSource): string | null {
  switch (source.kind) {
    case "reference":
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
