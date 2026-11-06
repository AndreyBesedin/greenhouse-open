import { contractReader, loadJson } from "../loadJson";
import { STORED_RUN_SCHEMA } from "../scene/generated/storedRunSchema";
import type { StoredRun } from "../scene/generated/storedRunTypes";

/** What is said of a failed epoch the simulator kept no reason for: one that
 * failed before epochs said why. */
export const NO_REASON_KEPT = "the simulator kept no reason for it";

/** Why a stored epoch failed, as the list of runs keeps it (`StoredRun.reason`),
 * or why that cannot be read. A position says only that it failed. */
export type FailureLoad =
  | { status: "loaded"; reason: string }
  | { status: "unavailable"; reason: string };

const readRun = contractReader<StoredRun>(
  STORED_RUN_SCHEMA,
  "the run's answer is not what the viewer reads",
);

/** Asks the simulator for a stored epoch (`GET /api/runs/{run}/epochs/{n}`, at
 * `url`) and reads why it failed. */
export async function loadFailure(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<FailureLoad> {
  const answer = await loadJson(url, readRun, fetchFn);
  return answer.status === "loaded"
    ? { status: "loaded", reason: answer.value.reason ?? NO_REASON_KEPT }
    : answer;
}

/** A failed run's page, in a sentence: why, once it is read. */
export function failedText(reason: string | null): string {
  return reason === null ? "This run failed." : `This run failed: ${reason}.`;
}
