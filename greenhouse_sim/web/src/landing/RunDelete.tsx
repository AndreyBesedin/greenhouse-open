import { type RefObject, useEffect, useId, useRef, useState } from "react";

import { Button } from "../design/Button";
import { deleteRun, notDeleted } from "./runActions";
import { isComputing, runKey, type StoredRun } from "./storedRuns";

/** What Delete says on hover (P22.7), and of a run being computed. */
export const DELETE_NOTE = "Delete this run and what it kept; asks first";
export const STOP_AND_DELETE_NOTE = "Stop this run, then delete it and what it kept; asks first";

/** What Delete's question says of a run being computed, before its answers. */
export const STOPS_FIRST =
  "This run is being computed: deleting it stops it first, then deletes it and what it kept.";

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

  /** Asks for `run` to be deleted, stopped first if it is being computed, and
   * says whether it was. */
  async function remove(run: StoredRun): Promise<boolean> {
    const answer = await deleteRun(run);
    if (answer === "stopping") {
      // Asked to stop, its worker has not looked yet. The row may have moved on
      // since it was read: it is what is said of it.
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
 * run, for whoever hears the button. A run `computing` is stopped before it is
 * deleted, as the question says first. `onDelete` says whether the run went: if it
 * did, its row goes with it, and the keyboard to `whenGone`, the list's heading,
 * rather than to the page's body. */
export function RunDelete({
  name,
  computing,
  onDelete,
  whenGone,
}: {
  name: string;
  computing: boolean;
  onDelete: () => Promise<boolean>;
  whenGone: RefObject<HTMLElement | null>;
}) {
  const said = useId();
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
      const heading = whenGone.current;
      // Focusable only from now: a heading always focusable would be the first
      // thing a dialog's showModal() puts the keyboard on.
      if (heading !== null && !heading.hasAttribute("tabindex")) {
        heading.tabIndex = -1;
      }
      heading?.focus();
    }
    setConfirming(false);
  }

  return confirming ? (
    <span className="landing-confirm">
      {computing && (
        <span id={said} className="landing-confirm-note">
          {STOPS_FIRST}
        </span>
      )}
      <Button
        tone="danger"
        aria-describedby={computing ? said : undefined}
        onClick={() => void confirmed()}
      >
        {computing ? `Stop and delete ${name}` : `Delete ${name}`}
      </Button>
      <Button
        ref={keep}
        aria-describedby={computing ? said : undefined}
        onClick={() => setConfirming(false)}
      >
        Keep it
      </Button>
    </span>
  ) : (
    <Button
      ref={pressed}
      className="landing-run-action landing-run-delete"
      aria-label={`Delete ${name}`}
      title={computing ? STOP_AND_DELETE_NOTE : DELETE_NOTE}
      onClick={() => setConfirming(true)}
    >
      Delete
    </Button>
  );
}
