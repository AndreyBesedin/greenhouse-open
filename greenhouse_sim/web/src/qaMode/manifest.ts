import { contractReader, loadJson } from "../loadJson";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import { RUN_MANIFEST_SCHEMA } from "./generated/runManifestSchema";
import type { RunManifest as ServedManifest } from "./generated/runManifestTypes";
import { VERSION_SCHEMA } from "./generated/versionSchema";
import type { Version } from "./generated/versionTypes";

/** The simulator the viewer is talking to, as it says itself
 * (`GET /api/version`): its version and the commit it runs from. */
export interface ServedVersion {
  version: string;
  commit: string;
}

/** What a scenario's run is made from, as the simulator reads it from the
 * scenario's manifest (`GET /api/scenarios/{id}/manifest`, P09.6). */
export interface RunManifest {
  scenarioId: string;
  /** The format its manifest is written in, and the digest of its content
   * that tells this version from another. */
  format: number;
  version: string;
  seed: number;
  /** Its start date, as the manifest writes it, its days, and the day a
   * viewer opens it on, if its manifest names one. */
  startDate: string;
  days: number;
  openingDay: number | null;
  /** The models it runs: its crop's, "simple" or "organ", and variety; its
   * prescribed airflow's kind; and its weather, by name and kind, its clouds
   * and wind as QA overrides them. */
  cropModel: string;
  variety: string;
  airflow: string;
  weather: string;
  weatherKind: string;
  cloudCoverPct: number | null;
  windFromDeg: number | null;
  /** The model each part of its run runs, and its version, by part, as its
   * manifest chooses them (P14.1, P14.2): the weather's, the air field's,
   * the crop's and the crop walk's. */
  models: Readonly<Record<string, { model: string; version: number }>>;
}

export type ServedVersionState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; served: ServedVersion };

export type RunManifestState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; manifest: RunManifest };

export const VERSION_URL = "/api/version";
// The commit of a simulator that is not run from a git checkout, and of a
// viewer not built in one.
export const UNKNOWN_COMMIT = "unknown";

/** Where the manifest of a scenario's run is published: under the weather
 * the run is asked for, the rest of the run making no difference to it. */
export function runManifestUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "manifest", runParameters(run, ["weather"]));
}

const readVersion = contractReader<Version>(
  VERSION_SCHEMA,
  "the simulator's version is not what the viewer expects",
);
const readManifest = contractReader<ServedManifest>(
  RUN_MANIFEST_SCHEMA,
  "the run's manifest is not what the viewer expects",
);

/** The simulator's version, checked rather than trusted. */
export function parseServedVersion(body: unknown): ServedVersion {
  const { version, commit } = readVersion(body);
  return { version, commit };
}

/** A run's manifest, checked rather than trusted. */
export function parseRunManifest(body: unknown): RunManifest {
  const served = readManifest(body);
  return {
    scenarioId: served.scenario_id,
    format: served.schema_version,
    version: served.version,
    seed: served.random_seed,
    startDate: served.start_date,
    days: served.duration_days,
    openingDay: served.opening_day,
    cropModel: served.crop_model,
    variety: served.variety,
    airflow: served.airflow,
    weather: served.weather,
    weatherKind: served.weather_kind,
    cloudCoverPct: served.cloud_cover_pct,
    windFromDeg: served.wind_from_deg,
    models: served.models,
  };
}

/** Fetches the simulator's version. */
export async function loadServedVersion(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<ServedVersionState> {
  const answer = await loadJson(url, parseServedVersion, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", served: answer.value } : answer;
}

/** Fetches a run's manifest, from its `runManifestUrl`. */
export async function loadRunManifest(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<RunManifestState> {
  const answer = await loadJson(url, parseRunManifest, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", manifest: answer.value } : answer;
}

const CROP_MODELS: Readonly<Record<string, string>> = {
  organ: "organ by organ",
  simple: "the simple daily model",
};

/** A run's manifest in words, a line for each of its parts. */
export function describeManifest(manifest: RunManifest): {
  scenario: string;
  seed: string;
  season: string;
  crop: string;
  airflow: string;
  weather: string;
  models: string;
} {
  const overrides = [
    ...(manifest.cloudCoverPct === null ? [] : [`clouds ${manifest.cloudCoverPct}%`]),
    ...(manifest.windFromDeg === null ? [] : [`wind from ${manifest.windFromDeg}°`]),
  ];
  const weatherName = manifest.weather === "default" ? "its own" : manifest.weather;
  return {
    scenario: `${manifest.scenarioId}, version ${manifest.version}, format ${manifest.format}`,
    seed: String(manifest.seed),
    season: `from ${manifest.startDate}, ${manifest.days} days${
      manifest.openingDay === null ? "" : `, opening on day ${manifest.openingDay}`
    }`,
    crop: `${manifest.variety}, ${CROP_MODELS[manifest.cropModel] ?? manifest.cropModel}`,
    airflow: `${manifest.airflow}, prescribed`,
    weather: [`${weatherName}, ${manifest.weatherKind}`, ...overrides].join(", "),
    models: Object.entries(manifest.models)
      .map(([part, run]) => `${part.replaceAll("_", " ")}: ${run.model} v${run.version}`)
      .join(", "),
  };
}
