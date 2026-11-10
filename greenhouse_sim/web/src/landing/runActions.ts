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

/** Deletes a run the simulator keeps. Its refusal of one being computed has no
 * words for a person: those are read off the run's row, by `notDeleted`. */
export async function deleteRun(
  { run_id, epoch }: Epoch,
  fetchFn: typeof fetch = fetch,
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

/** Why a run is not deleted yet, as its row reads: `name` is what the row calls
 * it. One over by its status was being computed as it was asked, taken up again
 * since its row was read. */
export function notDeleted(run: Pick<StoredRun, "status" | "stopping">, name: string): string {
  const named = `${name.charAt(0).toUpperCase()}${name.slice(1)}`;
  if (!isComputing(run)) {
    return `${named} is still being written: try again.`;
  }
  if (run.stopping) {
    return `${named} is stopping: delete it once it reads Interrupted.`;
  }
  return run.status === "queued"
    ? `${named} is waiting for a worker: stop it, then delete it.`
    : `${named} is still being computed: stop it, then delete it.`;
}
