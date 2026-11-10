import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { Button } from "../design/Button";
import { Field } from "../design/Field";
import { LinkButton } from "../design/LinkButton";
import { Notice } from "../design/Notice";
import { forkedText } from "../replay/timeline";
import { DEFAULT_WEATHER, type ScenarioSummary } from "../scenarios";
import { weatherName } from "../weather/WeatherPanel";
import { copyAddress, replayAddress } from "./paths";
import { RunControls } from "./RunControls";
import { RunDelete, useRunDeletion } from "./RunDelete";
import { ReplayLink, RunFailure, RunProgress, RunStatus, RunUsage } from "./RunParts";
import { notDoneText } from "./runActions";
import { DEFAULT_PACE_S, startRun } from "./startRun";
import { type StoredRun, startedText, whoIs } from "./storedRuns";

/** A run, as a list of one scenario's calls it. */
function nameOf(run: StoredRun): string {
  return `the run with ${whoIs(run)}`;
}

/** A scenario's crop, in words, as its summary says it. */
export function cropText({ plants, crop_model }: ScenarioSummary): string {
  const grown = crop_model === undefined ? "" : `, grown by the ${crop_model} crop model`;
  return `${plants} ${plants === 1 ? "plant" : "plants"}${grown}`;
}

/** A field's control as the start page draws it: `Field` draws none (P19.7). */
function landed(className: string): string {
  return `${className} landing-input`;
}

/** Why a run's days are refused, as entered: none if they are whole, from one to
 * the scenario's own (decision 0075). */
export function daysProblem(days: string, most: number): string | undefined {
  const count = Number(days);
  return days !== "" && Number.isInteger(count) && count >= 1 && count <= most
    ? undefined
    : `From 1 to its ${most} days.`;
}

/** The runs of a scenario the simulator has kept, with a way to start another,
 * to stop, resume and remove one (P17.5, decision 0065). A run is started for
 * its days and under its weather, its scenario's own unless others are chosen,
 * and its crop is the scenario's, which a new scenario made from it changes
 * (P22.4, decision 0075). It leads with the form for a new run, and lists the
 * runs under it. A run started is a worker's, beside any others, and the page
 * goes to its replay. A modal dialog: the browser keeps the keyboard in it and
 * closes it on Escape. */
export function RunsDialog({
  scenario,
  runs,
  navigate,
  onClose,
  onChanged,
}: {
  scenario: ScenarioSummary;
  /** The scenario's runs, the newest first. */
  runs: readonly StoredRun[];
  /** Goes to another page. */
  navigate: (address: string) => void;
  onClose: () => void;
  /** The runs kept have changed: ask for them again. */
  onChanged: () => void;
}) {
  const heading = useId();
  const newHeading = useId();
  const runsHeading = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const [days, setDays] = useState(String(scenario.duration_days));
  const [weather, setWeather] = useState(DEFAULT_WEATHER);
  const [seed, setSeed] = useState("");
  const [pace, setPace] = useState(DEFAULT_PACE_S);
  const weathers = scenario.weathers ?? [DEFAULT_WEATHER];
  const refusedDays = daysProblem(days, scenario.duration_days);
  const deletion = useRunDeletion(runs, nameOf, onChanged);
  // A second press of Start while the first is answered would be a second run.
  const [starting, setStarting] = useState(false);

  // Started, the page goes still starting. A browser that keeps a page as it
  // goes (its back-forward cache) gives it back so on Back, dialog and all:
  // the form is ready for another run then. A page loaded anew is not starting.
  useEffect(() => {
    function shownAgain(event: PageTransitionEvent): void {
      if (event.persisted) {
        setStarting(false);
      }
    }
    window.addEventListener("pageshow", shownAgain);
    return () => window.removeEventListener("pageshow", shownAgain);
  }, []);

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
    if (refusedDays !== undefined) {
      return;
    }
    setStarting(true);
    // Its own days are asked for as none, as its own weather is: the same run.
    // Fewer are sent as the whole number accepted ("10.0" as "10"), since the
    // API reads an integer's digits.
    const count = Number(days);
    const fewer = count === scenario.duration_days ? "" : String(count);
    const answer = await startRun(scenario.id, {
      seed,
      secondsPerDay: pace,
      weather,
      days: fewer,
    });
    if (!answer.ok) {
      setStarting(false);
      deletion.setProblem(notDoneText("started", answer.problem));
      return;
    }
    // Still starting as the page goes, so that no second press is on the way.
    deletion.setProblem(null);
    onChanged();
    navigate(replayAddress(answer.value.run_id, answer.value.epoch, true));
  }

  return (
    <dialog ref={dialog} className="landing-dialog" aria-labelledby={heading} onClose={onClose}>
      <header className="landing-dialog-head">
        <div>
          <h2 id={heading} ref={title}>
            {scenario.name}
          </h2>
          <p>
            {scenario.id} · {scenario.description}
          </p>
        </div>
        <div className="landing-dialog-actions">
          <Button onClick={close}>Close</Button>
        </div>
      </header>

      <form
        className="landing-form"
        aria-labelledby={newHeading}
        onSubmit={(event) => void submit(event)}
      >
        <h3 id={newHeading} className="landing-form-heading">
          New run
        </h3>
        <p className="landing-crop">
          <span>Its crop: {cropText(scenario)}.</span>
          <LinkButton href={copyAddress(scenario.id)} size="compact">
            Make a new scenario from this one
          </LinkButton>
        </p>
        <Field
          label="Days"
          hint={`Up to its own ${scenario.duration_days}; a longer run is a scenario of its own.`}
          problem={refusedDays}
        >
          {(control) => (
            <input
              {...control}
              className={landed(control.className)}
              type="number"
              min={1}
              max={scenario.duration_days}
              step={1}
              required
              value={days}
              onChange={(event) => setDays(event.target.value)}
            />
          )}
        </Field>
        <Field label="Weather">
          {(control) => (
            <select
              {...control}
              className={landed(control.className)}
              value={weather}
              onChange={(event) => setWeather(event.target.value)}
            >
              {weathers.map((each) => (
                <option key={each} value={each}>
                  {weatherName(each)}
                </option>
              ))}
            </select>
          )}
        </Field>
        {/* How fast the run is computed, which is not how fast its replay shows
            it: the replay chooses that (P22.5). A paced worker writes a day
            once its clock has passed it, so a day takes no less. The hint is
            no wider than the days', so that the three fields keep one row. */}
        <Field
          label="Seconds to compute a day"
          hint="A day takes no less. Its replay has a speed of its own."
        >
          {(control) => (
            <input
              {...control}
              className={landed(control.className)}
              type="number"
              min={1}
              step={1}
              placeholder="As fast as it computes"
              value={pace}
              onChange={(event) => setPace(event.target.value)}
            />
          )}
        </Field>
        <Field
          label="Seed"
          hint="The default. With no seed, the run uses the scenario's own, so the same choices give the same run."
          size="compact"
          className="landing-seed"
        >
          {(control) => (
            <input
              {...control}
              className={landed(control.className)}
              type="text"
              inputMode="numeric"
              placeholder="The scenario's own"
              value={seed}
              onChange={(event) => setSeed(event.target.value.replace(/\D/g, ""))}
            />
          )}
        </Field>
        <Button type="submit" tone="primary" disabled={starting || refusedDays !== undefined}>
          Start run
        </Button>
        <p className="landing-note">
          A worker computes it beside the runs already going, or it waits for one. Its replay opens
          at the newest day.
        </p>
      </form>

      {deletion.problem !== null && (
        <Notice kind="problem" className="landing-dialog-notice">
          {deletion.problem}
        </Notice>
      )}
      {deletion.notOver !== null && (
        <Notice kind="problem" className="landing-dialog-notice">
          {deletion.notOver}
        </Notice>
      )}
      <h3 id={runsHeading} className="landing-runs-heading">
        Its runs
      </h3>
      {runs.length === 0 ? (
        <p className="landing-empty">No runs of this scenario yet.</p>
      ) : (
        <ul className="landing-runs" aria-labelledby={runsHeading}>
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
                    {run.weather === null ? "" : ` · ${weatherName(run.weather)}`}
                    {run.fork === null ? "" : ` · ${forkedText(run.fork)}`}
                    {when === "" ? "" : ` · ${when}`}
                  </span>
                </div>
                <RunStatus run={run} />
                <RunProgress run={run} name={`the run with ${who}`} />
                <ReplayLink run={run} label={`Replay the run with ${who}`} />
                <RunControls
                  key={run.status}
                  run={run}
                  name={`the run with ${who}`}
                  onChanged={() => {
                    deletion.forget();
                    onChanged();
                  }}
                />
                <RunDelete
                  name={nameOf(run)}
                  onDelete={() => deletion.remove(run)}
                  whenGone={title}
                />
                <RunUsage run={run} />
                <RunFailure run={run} />
              </li>
            );
          })}
        </ul>
      )}
    </dialog>
  );
}
