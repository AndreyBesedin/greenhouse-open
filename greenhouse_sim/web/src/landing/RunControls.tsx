import { useState } from "react";

import { resumeRun, stopRun } from "./runActions";
import { isComputing, type StoredRun } from "./storedRuns";

/** A worker's run, stopped while it is computed and resumed once it is
 * interrupted (P17.7, P17.9). `name` says which, for whoever hears the button.
 * Why it did nothing is said beside it. Given a `key` of the run's status by its
 * list, so that a problem does not outlast the state it was about. */
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
  const stopping = isComputing(run);
  // One with files missing cannot be carried on: what it would go on from is gone.
  if (!stopping && (run.status !== "interrupted" || run.damaged)) {
    return null;
  }

  async function act(): Promise<void> {
    setBusy(true);
    const answer = await (stopping ? stopRun(run) : resumeRun(run));
    setBusy(false);
    setProblem(answer.ok ? null : answer.problem);
    if (answer.ok) {
      onChanged();
    }
  }

  const word = stopping ? "Stop" : "Resume";
  return (
    <>
      <button
        type="button"
        className="landing-button"
        aria-label={`${word} ${name}`}
        disabled={busy}
        onClick={() => void act()}
      >
        {word}
      </button>
      {problem !== null && (
        <p role="alert" className="landing-note">
          {problem}
        </p>
      )}
    </>
  );
}
