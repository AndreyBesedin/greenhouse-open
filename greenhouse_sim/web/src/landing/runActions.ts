import { type Answered, refusal } from "../builder/api";
import { isComputing, parseStoredRun, type StoredRun } from "./storedRuns";

const UNREACHED = "The simulator could not be reached.";

/** How the simulator answers about a run it no longer has. */
const NOT_THERE = 404;
const GONE = "This run is no longer kept.";

/** How the simulator refuses to delete a run being computed. */
const STILL_COMPUTED = 409;

type Epoch = Pick<StoredRun, "run_id" | "epoch">;

/** A run in the words the simulator's refusals name it by, as a person reads it:
 * its identifier says nothing that the row it is on does not. A refusal that only
 * names it before saying why, as one for a limit it is past does, says why. */
function aboutThisRun(problem: string, { run_id, epoch }: Epoch): string {
  const named = `epoch ${epoch} of ${run_id}`;
  const said = problem.startsWith(`${named}: `) ? problem.slice(named.length + 2) : problem;
  return said.replaceAll(named, "this run");
}

// A word that begins with a capital and goes on in small letters, as a sentence's
// first does, and not a name such as CPU.
const SENTENCE_START = /^[A-Z](?=[a-z])/;

/** What was asked and not done, and why, in a sentence: "Not started: 2 runs
 * waiting for a worker, …", in the simulator's own words, which name a limit
 * and its figures. */
export function notDoneText(asked: "started" | "resumed", problem: string): string {
  const why = problem.replace(/\.$/, "").replace(SENTENCE_START, (first) => first.toLowerCase());
  return `Not ${asked}: ${why}.`;
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

async function deleteOnce(
  { run_id, epoch }: Epoch,
  fetchFn: typeof fetch,
): Promise<Answered<null> | "being computed"> {
  const url = `/api/runs/${encodeURIComponent(run_id)}/epochs/${epoch}/delete`;
  const response = await fetchFn(url, { method: "POST" }).catch(() => null);
  if (response === null) {
    return { ok: false, problem: UNREACHED };
  }
  if (response.status === STILL_COMPUTED) {
    return "being computed";
  }
  return response.ok ? { ok: true, value: null } : { ok: false, problem: await refusal(response) };
}

/** Deletes a run the simulator keeps, and one being computed too: it is stopped
 * first, then deleted. A worker of this simulator has stopped by the time it
 * answers; one it cannot signal stops at its next look at the store, and until
 * then the run is `stopping`, which a person reads off its row, by `notDeleted`. */
export async function deleteRun(
  run: Epoch,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<null> | "stopping"> {
  const first = await deleteOnce(run, fetchFn);
  if (first !== "being computed") {
    return first;
  }
  const stopped = await stopRun(run, fetchFn);
  if (!stopped.ok && stopped.problem === GONE) {
    return { ok: true, value: null };
  }
  if (stopped.ok && isComputing(stopped.value)) {
    return "stopping";
  }
  // Stopped, or ended between the two asks: over, it is deleted all the same.
  const after = await deleteOnce(run, fetchFn);
  if (after !== "being computed") {
    return after;
  }
  return stopped.ok ? "stopping" : stopped;
}

/** Why a run is not deleted yet, as its row reads: `name` is what the row calls
 * it. One being computed was asked to stop, and its worker has not looked yet; one
 * over by its status was being computed as it was asked, taken up again since its
 * row was read. */
export function notDeleted(run: Pick<StoredRun, "status">, name: string): string {
  const named = `${name.charAt(0).toUpperCase()}${name.slice(1)}`;
  return isComputing(run)
    ? `${named} is stopping: it can be deleted once it reads Interrupted.`
    : `${named} is still being written: try again.`;
}
