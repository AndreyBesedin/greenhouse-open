import { type RefObject, useEffect, useRef, useState } from "react";

import { deleteRun, notDeleted } from "./runActions";
import { isComputing, runKey, type StoredRun } from "./storedRuns";

/** A list's deletions and what it says of one refused. Why a run not over is not
 * deleted is read off its row, as `runs` has it now: it follows the row, and goes
 * once the row is over or gone. `problem` stays until something clears it, and is
 * the list's to use for its other refusals. `nameOf` is what a row calls its run. */
export function useRunDeletion(
  runs: readonly StoredRun[],
  nameOf: (run: StoredRun) => string,
  onChanged: () => void,
) {
  const [problem, setProblem] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const refusedRun = runs.find((run) => runKey(run) === refused) ?? null;
  const running = refusedRun !== null && isComputing(refusedRun) ? refusedRun : null;

  // Not said again if the same run comes to be computed again, once resumed.
  useEffect(() => {
    if (refused !== null && running === null) {
      setRefused(null);
    }
  }, [refused, running]);

  /** Asks for `run` to be deleted, and says whether it was. */
  async function remove(run: StoredRun): Promise<boolean> {
    const answer = await deleteRun(run);
    if (answer === "being computed") {
      // The row may have moved on since it was read: it is what is said of it.
      const over = !isComputing(run);
      setProblem(over ? notDeleted(run, nameOf(run)) : null);
      setRefused(over ? null : runKey(run));
      onChanged();
      return false;
    }
    setRefused(null);
    setProblem(answer.ok ? null : answer.problem);
    if (answer.ok) {
      onChanged();
    }
    return answer.ok;
  }

  return {
    problem,
    setProblem,
    notOver: running === null ? null : notDeleted(running, nameOf(running)),
    remove,
    /** What was said was of the run as it stood, and it has changed. */
    forget: () => {
      setProblem(null);
      setRefused(null);
    },
  };
}

/** A run's Delete, in two steps, on every list of runs: pressed, it asks on a line
 * of its own, with the keyboard on the answer that loses nothing. `name` says which
 * run, for whoever hears the button. `onDelete` says whether the run went: if it
 * did, its row goes with it, and the keyboard to `whenGone`, the list's heading,
 * rather than to the page's body. */
export function RunDelete({
  name,
  onDelete,
  whenGone,
}: {
  name: string;
  onDelete: () => Promise<boolean>;
  whenGone: RefObject<HTMLElement | null>;
}) {
  const [confirming, setConfirming] = useState(false);
  // What had the keyboard is off the page while it asks, and back once it has.
  const pressed = useRef<HTMLButtonElement>(null);
  const keep = useRef<HTMLButtonElement>(null);
  const asked = useRef(false);
  useEffect(() => {
    if (confirming) {
      keep.current?.focus();
    } else if (asked.current) {
      pressed.current?.focus();
    }
    asked.current = confirming;
  }, [confirming]);

  async function confirmed(): Promise<void> {
    if (await onDelete()) {
      // Not back on a button about to go.
      asked.current = false;
      whenGone.current?.focus();
    }
    setConfirming(false);
  }

  return confirming ? (
    <span className="landing-confirm">
      <button
        type="button"
        className="landing-button landing-button-danger"
        onClick={() => void confirmed()}
      >
        Delete {name}
      </button>
      <button
        ref={keep}
        type="button"
        className="landing-button"
        onClick={() => setConfirming(false)}
      >
        Keep it
      </button>
    </span>
  ) : (
    <button
      ref={pressed}
      type="button"
      className="landing-button landing-run-action landing-run-delete"
      aria-label={`Delete ${name}`}
      onClick={() => setConfirming(true)}
    >
      Delete
    </button>
  );
}
