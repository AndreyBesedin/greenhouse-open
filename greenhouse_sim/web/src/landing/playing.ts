import { loadPlayback } from "../scene/playback";
import type { StoredRun } from "./storedRuns";

/** What names a stored epoch, among the runs the simulator keeps. */
export function runKey(run: Pick<StoredRun, "run_id" | "epoch">): string {
  return `${run.run_id}/${run.epoch}`;
}

/** The stored epochs that the scenarios' playbacks are playing now. */
export type Playing = { status: "loaded"; epochs: ReadonlySet<string> };

/**
 * Which of the scenarios' stored epochs are the ones their playbacks are
 * playing. A scenario has one playback, which a link to follow it reaches
 * whatever run it plays by then, so only an epoch that is the playback's
 * own is followed from the page: any other would attach to a replacement
 * (decision 0065, a run's address names its run and its epoch).
 */
export async function loadPlaying(
  scenarioIds: readonly string[],
  fetchFn: typeof fetch = fetch,
): Promise<Playing> {
  const epochs = new Set<string>();
  const answers = await Promise.all(scenarioIds.map((id) => loadPlayback(id, fetchFn)));
  for (const answer of answers) {
    if (answer.status === "loaded") {
      epochs.add(runKey({ run_id: answer.state.runId, epoch: answer.state.epoch }));
    }
  }
  return { status: "loaded", epochs };
}
