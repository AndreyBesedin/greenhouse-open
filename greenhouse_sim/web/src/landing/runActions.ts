import { type Answered, refusal } from "../builder/api";
import { parseStoredRun, type StoredRun } from "./storedRuns";

/** Why a run has no worker to stop: nothing here computes it by that route. */
const NO_WORKER =
  "No worker of this simulator has this run. One the viewer plays stops with its playback, and one whose worker is gone soon reads Interrupted.";

const UNREACHED = "The simulator could not be reached.";

/** How the simulator answers a stop of a run no worker of its has. */
const NOT_ITS_OWN = 404;

type Epoch = Pick<StoredRun, "run_id" | "epoch">;

/** A run in the words the simulator's refusals name it by, as a person reads it:
 * its identifier says nothing that the row it is on does not. */
function aboutThisRun(problem: string, { run_id, epoch }: Epoch): string {
  return problem.replaceAll(`epoch ${epoch} of ${run_id}`, "this run");
}

async function ask(
  { run_id, epoch }: Epoch,
  action: "stop" | "resume",
  refused: (response: Response) => Promise<string>,
  fetchFn: typeof fetch,
): Promise<Answered<StoredRun>> {
  const url = `/api/runs/${encodeURIComponent(run_id)}/epochs/${epoch}/${action}`;
  try {
    const response = await fetchFn(url, { method: "POST" });
    if (!response.ok) {
      return { ok: false, problem: await refused(response) };
    }
    const run = parseStoredRun(await response.json());
    return run === null
      ? { ok: false, problem: "The simulator's answer is not a run." }
      : { ok: true, value: run };
  } catch {
    return { ok: false, problem: UNREACHED };
  }
}

/** Stops a run being computed or waiting for a worker: it is left interrupted,
 * with what it had committed, and can be resumed. */
export function stopRun(run: Epoch, fetchFn: typeof fetch = fetch): Promise<Answered<StoredRun>> {
  return ask(
    run,
    "stop",
    async (response) =>
      response.status === NOT_ITS_OWN ? NO_WORKER : aboutThisRun(await refusal(response), run),
    fetchFn,
  );
}

/** Asks a worker to carry an interrupted run on from its last commit, as fast as
 * it computes: an epoch's manifest does not say the pace it was started at. */
export function resumeRun(run: Epoch, fetchFn: typeof fetch = fetch): Promise<Answered<StoredRun>> {
  return ask(
    run,
    "resume",
    async (response) => aboutThisRun(await refusal(response), run),
    fetchFn,
  );
}
