import { DAY_S } from "../clock";
import { contractCheck, loadJson } from "../loadJson";
import { STORED_RUN_SCHEMA } from "../scene/generated/storedRunSchema";
import type { Status, StoredRun } from "../scene/generated/storedRunTypes";

export type { Status, StoredRun };

/** Every run the simulator has kept, the newest started first
 * (`GET /api/runs`, P17.5). */
export const STORED_RUNS_URL = "/api/runs";

/** How long after an answer the runs kept are asked for again, while one is
 * still being computed. */
export const RUNS_ASKED_EVERY_MS = 2000;

export type StoredRunsState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; runs: StoredRun[] };

const checkRun = contractCheck<StoredRun>(STORED_RUN_SCHEMA, "the run");

/** The runs in a response body, checked rather than trusted. */
export function parseStoredRuns(body: unknown): StoredRun[] {
  if (!Array.isArray(body)) {
    throw new Error("expected a list of runs");
  }
  return body.map((item: unknown, index) => {
    const checked = checkRun(item);
    if (!checked.ok) {
      throw new Error(`run ${index} is not a stored run`);
    }
    return checked.value;
  });
}

/** The run in a response body, checked rather than trusted; null if it is not
 * one. */
export function parseStoredRun(body: unknown): StoredRun | null {
  const checked = checkRun(body);
  return checked.ok ? checked.value : null;
}

/** Asks the simulator for the runs it has kept; any failure becomes
 * `unavailable`. */
export async function loadStoredRuns(fetchFn: typeof fetch = fetch): Promise<StoredRunsState> {
  const answer = await loadJson(STORED_RUNS_URL, parseStoredRuns, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", runs: answer.value } : answer;
}

/** How many runs each scenario has kept. */
export function runCounts(runs: readonly StoredRun[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const run of runs) {
    counts.set(run.scenario_id, (counts.get(run.scenario_id) ?? 0) + 1);
  }
  return counts;
}

/** A scenario's run count, in words. */
export function runCountText(count: number): string {
  return count === 0 ? "no runs" : count === 1 ? "1 run" : `${count} runs`;
}

/** What a status is called to a person; a status is also a word, never a
 * colour alone. */
export const STATUS_LABEL: Record<Status, string> = {
  queued: "Queued",
  running: "Running",
  finished: "Finished",
  failed: "Failed",
  interrupted: "Interrupted",
};

/** How far a run is computed, in whole days: "41 of 120 days", or "41
 * days" if its length is not known. */
export function progressText(run: StoredRun): string {
  const done = Math.floor(run.frontier_s / DAY_S);
  return run.duration_s === null
    ? `${done} days`
    : `${done} of ${Math.round(run.duration_s / DAY_S)} days`;
}

/** How much of a run is computed, from 0 to 1. */
export function progressShare(run: StoredRun): number {
  return run.progress === null ? 0 : Math.min(1, Math.max(0, run.progress));
}

const KILOBYTE = 1024;
const MEGABYTE = KILOBYTE * KILOBYTE;

/** A size in bytes, in the unit that reads best. */
export function sizeText(bytes: number): string {
  if (bytes >= MEGABYTE) {
    return `${(bytes / MEGABYTE).toFixed(1)} MB`;
  }
  return bytes >= KILOBYTE ? `${Math.round(bytes / KILOBYTE)} kB` : `${bytes} B`;
}

/** What the runs kept hold, in a line: how many, and the size of their
 * objects in all (`size_bytes` of each); nothing when none is kept, which the
 * list says in its own words. */
export function keptText(runs: readonly StoredRun[]): string | null {
  if (runs.length === 0) {
    return null;
  }
  const bytes = runs.reduce((total, run) => total + run.size_bytes, 0);
  return `${runs.length === 1 ? "1 run" : `${runs.length} runs`} kept, ${sizeText(bytes)}`;
}

/** What that size is and is not, said where the line is. */
export const KEPT_SIZE_NOTE =
  "The size of the runs' own objects (their records and checkpoints), not of the disk they are on.";

/** The day a run was started, in UTC so that it reads the same wherever it is
 * read; nothing when its start is not known. */
export function startedText(run: StoredRun): string {
  if (run.created_at === null) {
    return "";
  }
  const started = new Date(run.created_at);
  return Number.isNaN(started.getTime())
    ? ""
    : started.toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** Whether a run is still being computed, when it can be followed and not
 * deleted. */
export function isComputing(run: StoredRun): boolean {
  return run.status === "queued" || run.status === "running";
}
