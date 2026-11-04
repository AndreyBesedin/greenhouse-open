import { type Answered, refusal } from "../builder/api";
import { parseStoredRun, type StoredRun } from "./storedRuns";

const UNREACHED = "The simulator could not be reached.";

/** How the simulator answers about a run it no longer has. */
const NOT_THERE = 404;
const GONE = "This run is no longer kept.";

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
 * with what it had committed, and can be resumed. A worker the simulator cannot
 * signal stops at its next look at the store: the run answered says `stopping`
 * until then. */
export function stopRun(run: Epoch, fetchFn: typeof fetch = fetch): Promise<Answered<StoredRun>> {
  return ask(
    run,
    "stop",
    async (response) =>
      response.status === NOT_THERE ? GONE : aboutThisRun(await refusal(response), run),
    fetchFn,
  );
}

/** Asks a worker to carry an interrupted run on from its last commit, at the pace
 * it was asked for, which the simulator keeps with the run. */
export function resumeRun(run: Epoch, fetchFn: typeof fetch = fetch): Promise<Answered<StoredRun>> {
  return ask(
    run,
    "resume",
    async (response) => aboutThisRun(await refusal(response), run),
    fetchFn,
  );
}
