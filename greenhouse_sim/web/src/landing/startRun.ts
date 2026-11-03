import { type Answered, refusal } from "../builder/api";
import { parseStoredRun, type StoredRun } from "./storedRuns";

/** The pace a run is started at unless another is asked for, in real seconds
 * for a simulated day, as a person enters it. */
export const DEFAULT_PACE_S = "10";

/** What a run is asked for at, as a person enters it: its seed, or none for the
 * scenario's own, and how many real seconds a simulated day takes, or none for
 * as fast as it can be computed. */
export interface RunAsked {
  seed: string;
  secondsPerDay: string;
}

/** A run of a scenario given to a worker, beside any others of it (decision
 * 0065): the epoch it is, queued, or why it was refused. */
export async function startRun(
  scenarioId: string,
  { seed, secondsPerDay }: RunAsked,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<StoredRun>> {
  const query = new URLSearchParams();
  if (seed !== "") {
    query.set("seed", seed);
  }
  if (secondsPerDay !== "") {
    query.set("seconds_per_day", secondsPerDay);
  }
  const url = `/api/scenarios/${encodeURIComponent(scenarioId)}/runs?${query}`;
  try {
    const response = await fetchFn(url, { method: "POST" });
    if (!response.ok) {
      return { ok: false, problem: await refusal(response) };
    }
    const run = parseStoredRun(await response.json());
    return run === null
      ? { ok: false, problem: "the simulator's answer is not a run" }
      : { ok: true, value: run };
  } catch (error) {
    return { ok: false, problem: error instanceof Error ? error.message : String(error) };
  }
}
