import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { refusal } from "../builder/api";
import type { ScenarioSummary } from "../scenarios";
import { loadPlayback, parsePlayback } from "../scene/playback";
import { followAddress } from "./follow";
import { viewerAddress } from "./paths";
import { runKey } from "./playing";
import { RunProgress, StatusChip } from "./RunParts";
import { type StoredRun, sizeText, startedText } from "./storedRuns";

/** The pace a run is started at unless another is entered, in real seconds
 * for a simulated day. */
const DEFAULT_PACE_S = "10";

/** What starting a run did: made one, or found the scenario's playback
 * already playing that run and epoch, which starting it again only resumes. */
type Outcome = { kind: "started" | "resumed"; epoch: number; layout: string };

/** The runs of a scenario the simulator has kept, with a way to start another
 * and to remove one (P17.5, decision 0065). A modal dialog: the browser keeps
 * the keyboard in it and closes it on Escape. */
export function RunsDialog({
  scenario,
  runs,
  followed,
  newRun = false,
  onClose,
  onChanged,
}: {
  scenario: ScenarioSummary;
  /** The scenario's runs, the newest first. */
  runs: readonly StoredRun[];
  /** The stored epochs that playbacks are playing now (`loadPlaying`): those
   * a link to follow reaches, and not a replacement. */
  followed: ReadonlySet<string>;
  /** Whether the form for a new run is open as the dialog opens. */
  newRun?: boolean;
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
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

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

  async function startRun(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    // An empty seed asks for the scenario's own: none would keep the seed
    // of the playback now in place.
    const query = new URLSearchParams({
      seconds_per_day: pace,
      seed: seed === "" ? "default" : seed,
    });
    // What plays before, to tell a run made from one only resumed.
    const before = await loadPlayback(scenario.id);
    const response = await fetch(
      `/api/scenarios/${encodeURIComponent(scenario.id)}/playback/start?${query}`,
      { method: "POST" },
    ).catch(() => null);
    if (response === null || !response.ok) {
      setProblem(
        response === null ? "The simulator could not be reached." : await refusal(response),
      );
      return;
    }
    const state = parsePlayback(await response.json().catch(() => null));
    if (state === null) {
      setProblem("The simulator's answer is not the playback's state.");
      return;
    }
    const resumed =
      before.status === "loaded" &&
      before.state.runId === state.runId &&
      before.state.epoch === state.epoch;
    setProblem(null);
    setOutcome({ kind: resumed ? "resumed" : "started", epoch: state.epoch, layout: state.layout });
    setFormOpen(false);
    setSeed("");
    onChanged();
  }

  /** The playback it found started over, as a new epoch of the same run. */
  async function startAgain(): Promise<void> {
    const response = await fetch(
      `/api/scenarios/${encodeURIComponent(scenario.id)}/playback/restart`,
      { method: "POST" },
    ).catch(() => null);
    if (response === null || !response.ok) {
      setProblem(
        response === null ? "The simulator could not be reached." : await refusal(response),
      );
      return;
    }
    const state = parsePlayback(await response.json().catch(() => null));
    setProblem(null);
    setOutcome({ kind: "started", epoch: state?.epoch ?? 0, layout: state?.layout ?? "default" });
    onChanged();
  }

  async function remove(run: StoredRun): Promise<void> {
    const response = await fetch(
      `/api/runs/${encodeURIComponent(run.run_id)}/epochs/${run.epoch}/delete`,
      {
        method: "POST",
      },
    ).catch(() => null);
    setConfirming(null);
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
          <button type="button" className="landing-button" onClick={onClose}>
            Close
          </button>
        </div>
      </header>

      {formOpen && (
        <form className="landing-form" onSubmit={(event) => void startRun(event)}>
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
              required
              value={pace}
              onChange={(event) => setPace(event.target.value)}
            />
          </label>
          <button type="submit" className="landing-button landing-button-primary">
            Start run
          </button>
          <p className="landing-note">
            Starting a run replaces the one now playing for this scenario, which stays in the list.
          </p>
        </form>
      )}

      {problem !== null && <p role="alert">{problem}</p>}
      {outcome?.kind === "started" && (
        <p role="status">
          Run started, as epoch {outcome.epoch}.{" "}
          <a href={followAddress(scenario.id, outcome.layout)}>Follow it in the viewer</a>.
        </p>
      )}
      {outcome?.kind === "resumed" && (
        <p role="status">
          That run is the one playing already, as epoch {outcome.epoch}: starting it again only
          resumes it, and runs nothing again.{" "}
          <a href={followAddress(scenario.id, outcome.layout)}>Follow it in the viewer</a>
          {" or "}
          <button type="button" className="landing-button" onClick={() => void startAgain()}>
            Start it again as a new epoch
          </button>
        </p>
      )}

      {runs.length === 0 ? (
        <p className="landing-empty">No runs of this scenario yet. Start one with New run.</p>
      ) : (
        <ul className="landing-runs">
          {runs.map((run) => {
            const key = `${run.run_id}/${run.epoch}`;
            const who = `${run.seed === null ? "the scenario's seed" : `seed ${run.seed}`}, epoch ${run.epoch}`;
            const when = startedText(run);
            return (
              <li key={key} className="landing-run">
                <div className="landing-run-name">
                  <strong>{run.seed === null ? "The scenario's seed" : `Seed ${run.seed}`}</strong>
                  <span>
                    epoch {run.epoch}
                    {when === "" ? "" : ` · ${when}`} · {sizeText(run.size_bytes)}
                  </span>
                </div>
                <StatusChip run={run} />
                <RunProgress run={run} name={`the run with ${who}`} />
                {followed.has(runKey(run)) && (
                  <a
                    href={followAddress(run.scenario_id, run.layout)}
                    className="landing-link-button"
                  >
                    Follow
                  </a>
                )}
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
