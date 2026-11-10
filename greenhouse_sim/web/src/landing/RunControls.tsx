import { useState } from "react";

import { Button } from "../design/Button";
import { Notice } from "../design/Notice";
import { notDoneText, resumeRun, stopRun } from "./runActions";
import { isComputing, isResumable, type StoredRun } from "./storedRuns";

/** A run, a worker's or a playback's, stopped while it is computed and resumed
 * once it is interrupted or ended by a limit (P17.7, P17.9, P18.5), with nothing to
 * press once it has been asked to stop and has not yet. `name` says which, for
 * whoever hears the button. Why it did nothing is said beside it: a resume
 * refused for a limit, in the simulator's words. Given a `key` of the run's status
 * by its list, so that a problem does not outlast the state it was about. */
export function RunControls({
  run,
  name,
  onChanged,
}: {
  run: StoredRun;
  name: string;
  /** The run has changed: ask for the runs again. */
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const computing = isComputing(run);
  if (!computing && !isResumable(run)) {
    return null;
  }

  async function act(): Promise<void> {
    setBusy(true);
    const answer = await (computing ? stopRun(run) : resumeRun(run));
    setBusy(false);
    if (!answer.ok) {
      setProblem(computing ? answer.problem : notDoneText("resumed", answer.problem));
    } else {
      setProblem(null);
    }
    if (answer.ok) {
      onChanged();
    }
  }

  const word = run.stopping ? "Stopping" : computing ? "Stop" : "Resume";
  return (
    <>
      <Button
        className="landing-run-action landing-run-control"
        aria-label={`${word} ${name}`}
        disabled={busy || run.stopping}
        onClick={() => void act()}
      >
        {word}
      </Button>
      {problem !== null && (
        <Notice kind="problem" className="landing-run-problem">
          {problem}
        </Notice>
      )}
    </>
  );
}
