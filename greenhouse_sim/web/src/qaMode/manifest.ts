import { type RunParts, runParameters, scenarioUrl } from "../scene/run";

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

/** Where the manifest of a scenario's run is published: under the weather
 * the run is asked for, the rest of the run making no difference to it. */
export function runManifestUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "manifest", runParameters(run, ["weather"]));
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumberOrNull(value: unknown): value is number | null {
  return value === null || typeof value === "number";
}

/** The simulator's version, checked rather than trusted. */
export function parseServedVersion(body: unknown): ServedVersion {
  if (!isObject(body) || typeof body.version !== "string" || typeof body.commit !== "string") {
    throw new Error("the simulator's version is not what the viewer expects");
  }
  return { version: body.version, commit: body.commit };
}

/** A run's manifest, checked rather than trusted. */
export function parseRunManifest(body: unknown): RunManifest {
  if (
    !isObject(body) ||
    typeof body.scenario_id !== "string" ||
    typeof body.schema_version !== "number" ||
    typeof body.version !== "string" ||
    typeof body.random_seed !== "number" ||
    typeof body.start_date !== "string" ||
    typeof body.duration_days !== "number" ||
    !isNumberOrNull(body.opening_day) ||
    typeof body.crop_model !== "string" ||
    typeof body.variety !== "string" ||
    typeof body.airflow !== "string" ||
    typeof body.weather !== "string" ||
    typeof body.weather_kind !== "string" ||
    !isNumberOrNull(body.cloud_cover_pct) ||
    !isNumberOrNull(body.wind_from_deg)
  ) {
    throw new Error("the run's manifest is not what the viewer expects");
  }
  return {
    scenarioId: body.scenario_id,
    format: body.schema_version,
    version: body.version,
    seed: body.random_seed,
    startDate: body.start_date,
    days: body.duration_days,
    openingDay: body.opening_day,
    cropModel: body.crop_model,
    variety: body.variety,
    airflow: body.airflow,
    weather: body.weather,
    weatherKind: body.weather_kind,
    cloudCoverPct: body.cloud_cover_pct,
    windFromDeg: body.wind_from_deg,
  };
}

/** Fetches what `parse` reads from `url`; every failure becomes
 * `unavailable`. */
async function loadChecked<T>(
  url: string,
  parse: (body: unknown) => T,
  fetchFn: typeof fetch,
): Promise<{ status: "loaded"; value: T } | { status: "unavailable"; reason: string }> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", value: parse(await response.json()) };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

/** Fetches the simulator's version. */
export async function loadServedVersion(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<ServedVersionState> {
  const answer = await loadChecked(url, parseServedVersion, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", served: answer.value } : answer;
}

/** Fetches a run's manifest, from its `runManifestUrl`. */
export async function loadRunManifest(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<RunManifestState> {
  const answer = await loadChecked(url, parseRunManifest, fetchFn);
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
  };
}
