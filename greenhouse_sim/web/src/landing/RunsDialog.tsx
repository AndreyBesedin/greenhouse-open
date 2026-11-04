import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { refusal } from "../builder/api";
import { forkedText } from "../replay/timeline";
import type { ScenarioSummary } from "../scenarios";
import { replayAddress, viewerAddress } from "./paths";
import { RunControls } from "./RunControls";
import { FollowLink, ReplayLink, RunProgress, StatusChip } from "./RunParts";
import { DEFAULT_PACE_S, startRun } from "./startRun";
import { type StoredRun, sizeText, startedText } from "./storedRuns";

/** How the simulator refuses to delete a run being computed. */
const STILL_COMPUTED = 409;

/** Who a run is, as a list of one scenario's says it. */
function whoIs(run: StoredRun): string {
  return `${run.seed === null ? "the scenario's seed" : `seed ${run.seed}`}, epoch ${run.epoch}`;
}

/** The runs of a scenario the simulator has kept, with a way to start another,
 * to stop, resume and remove one (P17.5, decision 0065). A run started is a
 * worker's, beside any others, and the page goes to its replay. A modal dialog:
 * the browser keeps the keyboard in it and closes it on Escape. */
export function RunsDialog({
  scenario,
  runs,
  newRun = false,
  navigate,
  onClose,
  onChanged,
}: {
  scenario: ScenarioSummary;
  /** The scenario's runs, the newest first. */
  runs: readonly StoredRun[];
  /** Whether the form for a new run is open as the dialog opens. */
  newRun?: boolean;
  /** Goes to another page. */
  navigate: (address: string) => void;
  onClose: () => void;
  /** The runs kept have changed: ask for them again. */
  onChanged: () => void;
}) {
  const heading = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const [formOpen, setFormOpen] = useState(newRun);
  const [seed, setSeed] = useState("");
  const [pace, setPace] = useState(DEFAULT_PACE_S);
  const [problem, setProblem] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  // A second press of Start while the first is answered would be a second run.
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const shown = dialog.current;
    if (shown !== null && !shown.open) {
      // A browser makes it modal; a DOM without that only opens it.
      if (typeof shown.showModal === "function") {
        shown.showModal();
      } else {
        shown.setAttribute("open", "");
      }
    }
  }, []);

  /** Closes the dialog as Escape does, for the browser to give focus back to
   * what had it, which it does not for a dialog merely taken off the page; its
   * `close` event says so to the page. A DOM without that only says so. */
  function close(): void {
    const shown = dialog.current;
    if (shown !== null && typeof shown.close === "function") {
      shown.close();
    } else {
      onClose();
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setStarting(true);
    const answer = await startRun(scenario.id, { seed, secondsPerDay: pace });
    setStarting(false);
    if (!answer.ok) {
      setProblem(answer.problem);
      return;
    }
    setProblem(null);
    // The form goes as the page does: no second press on the way, and none
    // left open on the page a person comes back to.
    setFormOpen(false);
    setSeed("");
    onChanged();
    navigate(replayAddress(answer.value.run_id, answer.value.epoch, true));
  }

  async function remove(run: StoredRun): Promise<void> {
    const response = await fetch(
      `/api/runs/${encodeURIComponent(run.run_id)}/epochs/${run.epoch}/delete`,
      {
        method: "POST",
      },
    ).catch(() => null);
    setConfirming(null);
    if (response?.status === STILL_COMPUTED) {
      setProblem(
        run.stopping
          ? `The run with ${whoIs(run)} is stopping: delete it once it reads Interrupted.`
          : `The run with ${whoIs(run)} is still being computed: stop it, then delete it.`,
      );
      return;
    }
    if (response === null || !response.ok) {
      setProblem(
        response === null ? "The simulator could not be reached." : await refusal(response),
      );
      return;
    }
    setProblem(null);
    onChanged();
  }

  return (
    <dialog ref={dialog} className="landing-dialog" aria-labelledby={heading} onClose={onClose}>
      <header className="landing-dialog-head">
        <div>
          <h2 id={heading}>{scenario.name}</h2>
          <p>
            {scenario.id} · {scenario.description}
          </p>
        </div>
        <div className="landing-dialog-actions">
          <a href={viewerAddress(scenario.id)} className="landing-link-button">
            Open in the viewer
          </a>
          <button type="button" className="landing-button" onClick={() => setFormOpen(!formOpen)}>
            New run
          </button>
          <button type="button" className="landing-button" onClick={close}>
            Close
          </button>
        </div>
      </header>

      {formOpen && (
        <form className="landing-form" onSubmit={(event) => void submit(event)}>
          <label className="landing-field">
            <span>Seed</span>
            <input
              className="landing-input"
              type="text"
              inputMode="numeric"
              placeholder="The scenario's own"
              value={seed}
              onChange={(event) => setSeed(event.target.value.replace(/\D/g, ""))}
            />
          </label>
          <label className="landing-field">
            <span>Seconds per simulated day</span>
            <input
              className="landing-input"
              type="number"
              min={1}
              step={1}
              placeholder="As fast as it computes"
              value={pace}
              onChange={(event) => setPace(event.target.value)}
            />
          </label>
          <button
            type="submit"
            className="landing-button landing-button-primary"
            disabled={starting}
          >
            Start run
          </button>
          <p className="landing-note">
            A worker computes it beside the runs already going, or it waits for one. Its replay
            opens at the newest day.
          </p>
        </form>
      )}

      {problem !== null && <p role="alert">{problem}</p>}
      {runs.length === 0 ? (
        <p className="landing-empty">No runs of this scenario yet. Start one with New run.</p>
      ) : (
        <ul className="landing-runs">
          {runs.map((run) => {
            const key = `${run.run_id}/${run.epoch}`;
            const who = whoIs(run);
            const when = startedText(run);
            return (
              <li key={key} className="landing-run">
                <div className="landing-run-name">
                  <strong>{run.seed === null ? "The scenario's seed" : `Seed ${run.seed}`}</strong>
                  <span>
                    epoch {run.epoch}
                    {run.fork === null ? "" : ` · ${forkedText(run.fork)}`}
                    {when === "" ? "" : ` · ${when}`} · {sizeText(run.size_bytes)}
                  </span>
                </div>
                <StatusChip run={run} />
                <RunProgress run={run} name={`the run with ${who}`} />
                <ReplayLink run={run} label={`Replay the run with ${who}`} />
                <FollowLink run={run} />
                <RunControls
                  key={run.status}
                  run={run}
                  name={`the run with ${who}`}
                  onChanged={() => {
                    // What a refused deletion said was of the run as it stood.
                    setProblem(null);
                    onChanged();
                  }}
                />
                {confirming === key ? (
                  <span className="landing-confirm">
                    <button
                      type="button"
                      className="landing-button landing-button-danger"
                      onClick={() => void remove(run)}
                    >
                      Delete the run with {who}
                    </button>
                    <button
                      type="button"
                      className="landing-button"
                      onClick={() => setConfirming(null)}
                    >
                      Keep it
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    className="landing-button"
                    aria-label={`Delete the run with ${who}`}
                    onClick={() => setConfirming(key)}
                  >
                    Delete
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </dialog>
  );
}
