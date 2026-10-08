import { pairsText, type ScheduledCommand, scheduleText } from "../scene/source";
import { checkField, type EnvironmentField, SUPPORTED_FIELD_VERSION } from "./field";

/** The air as a scenario's equipment drives it: the one field that depends on
 * how hard its equipment runs. */
export const CLIMATE_FIELD = "climate";

export type FieldState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "rejected"; problems: string[] }
  | { status: "loaded"; field: EnvironmentField };

/** What a scenario's field is asked for with: another of its layouts, which
 * its CFD solution depends on, and its equipment's levels, its doors and
 * vents and a moment of its climate run, which its climate depends on. */
export interface FieldChanges {
  layout?: string | undefined;
  levels?: Readonly<Record<string, number>> | undefined;
  openings?: Readonly<Record<string, number>> | undefined;
  /** Commands to its equipment after the start. */
  schedule?: readonly ScheduledCommand[] | undefined;
  /** Seconds into the climate run. */
  time?: number | undefined;
}

/** How long a climate run lasts, in seconds, as the simulator runs it. */
export const CLIMATE_RUN_S = 3600;

/** Where a scenario's field is published (`GET /api/scenarios/{id}/fields/{name}`),
 * with another of its layouts if one is named, and, for its climate, its
 * equipment at the levels set and its doors and vents open as set, at a
 * moment of its run. */
export function fieldUrl(scenarioId: string, name: string, changes: FieldChanges = {}): string {
  const base = `/api/scenarios/${encodeURIComponent(scenarioId)}/fields/${encodeURIComponent(name)}`;
  const climate = name === CLIMATE_FIELD;
  const levels = climate ? pairsText(changes.levels) : "";
  const openings = climate ? pairsText(changes.openings) : "";
  const schedule = climate ? scheduleText(changes.schedule) : "";
  const time = climate && changes.time !== undefined && changes.time > 0 ? changes.time : null;
  const parts = [
    ...(changes.layout === undefined ? [] : [`layout=${encodeURIComponent(changes.layout)}`]),
    ...(levels === "" ? [] : [`set=${levels}`]),
    ...(openings === "" ? [] : [`open=${openings}`]),
    ...(schedule === "" ? [] : [`schedule=${schedule}`]),
    ...(time === null ? [] : [`t=${time}`]),
  ];
  return parts.length === 0 ? base : `${base}?${parts.join("&")}`;
}

/** `?layout=` for another of a scenario's layouts, or nothing for its own. */
export function layoutQuery(layout: string | undefined): string {
  return layout === undefined ? "" : `?layout=${encodeURIComponent(layout)}`;
}

/** Fetches and checks a scenario's field; every failure becomes a state to show. */
export function loadField(
  scenarioId: string,
  name: string,
  changes: FieldChanges = {},
  fetchFn: typeof fetch = fetch,
): Promise<FieldState> {
  return fetchField(fieldUrl(scenarioId, name, changes), fetchFn);
}

/** Fetches and checks the field at `url`, from the simulator or a file it
 * wrote; every failure becomes a state to show. */
export async function fetchField(url: string, fetchFn: typeof fetch = fetch): Promise<FieldState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "schema_version" in body &&
      body.schema_version !== SUPPORTED_FIELD_VERSION
    ) {
      return {
        status: "rejected",
        problems: [
          `field version ${String(body.schema_version)} is not the ${SUPPORTED_FIELD_VERSION} this viewer reads`,
        ],
      };
    }
    const check = checkField(body);
    return check.ok
      ? { status: "loaded", field: check.field }
      : { status: "rejected", problems: check.problems };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}
