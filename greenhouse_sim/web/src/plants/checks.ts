import { contractReader, loadJson } from "../loadJson";
import { LAB_CHECKS_SCHEMA } from "./generated/labChecksSchema";
import type { LabChecks } from "./generated/labChecksTypes";

/** What the simulator's lab finds wrong with each of its plants on a run's
 * day (`GET /api/plants/checks`): the structure's rules each breaks, and
 * anything it did since the day before that a plant cannot. */
export type ChecksState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; day: number; problems: Record<string, string[]> };

export const PLANT_LAB_CHECKS_URL = "/api/plants/checks";

/** The checks, checked rather than trusted. */
export const labChecks = contractReader<LabChecks>(
  LAB_CHECKS_SCHEMA,
  "the checks are not what the viewer expects",
);

/** Asks the lab for its checks on a run, as `labRunQuery` writes it; any
 * failure becomes `unavailable`. */
/** Where the structure's rules are checked for a run of the lab. */
export function labChecksUrl(runQuery: string): string {
  return `${PLANT_LAB_CHECKS_URL}?${runQuery}`;
}

export async function loadLabChecks(
  runQuery: string,
  fetchFn: typeof fetch = fetch,
): Promise<ChecksState> {
  const answer = await loadJson(labChecksUrl(runQuery), labChecks, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", ...answer.value } : answer;
}
