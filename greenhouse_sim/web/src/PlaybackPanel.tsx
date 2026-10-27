import { DAY_S } from "./clock";
import { describeTime } from "./fields/ClimateTime";
import {
  followedMoment,
  type PlaybackCommand,
  type PlaybackLoad,
  type PlaybackState,
} from "./scene/playback";

/**
 * The run a view follows as it is played back (P10.2, decision 0041): which
 * run, its epoch, how fast it plays and where its clock stands across all
 * its days, with its controls, which every viewer and consumer of it
 * shares. Its play and pause are the view's, the climate run's own standing
 * aside (#270). The view draws the run at that clock's moment. A level or a
 * target set in the panels steers the run played back, through its plan
 * (P13.8), and the panel says why if its gateway refuses it; any other
 * change made here (a weather, a layout, a command removed) makes another
 * run, which the view then draws in its place, and says so.
 */
export function PlaybackPanel({
  load,
  days,
  changed,
  refusal = null,
  onCommand,
  onStart,
  onOwnRun,
  onStop,
}: {
  load: PlaybackLoad;
  /** How many days the run lasts, once the viewer knows. */
  days: number | null;
  /** What the view changes of the scenario's own run, if anything. */
  changed: readonly string[];
  /** Why the run's gateway refused what the panels last set, if it did. */
  refusal?: string | null;
  onCommand: (command: PlaybackCommand) => void;
  onStart: () => void;
  /** Draws the run played back again, without the view's changes. */
  onOwnRun: () => void;
  onStop: () => void;
}) {
  return (
    <section className="playback" aria-label="Run played back">
      <Standing load={load} days={days} onCommand={onCommand} onStart={onStart} />
      {refusal !== null && (
        <p role="alert" data-testid="playback-refused">
          The run refused what was set: {refusal}.
        </p>
      )}
      {changed.length > 0 && (
        <p role="alert" data-testid="playback-another-run">
          This view draws another run than the one played back: it changes {changed.join(", ")}.{" "}
          <button type="button" onClick={onOwnRun}>
            Draw the run played back
          </button>
        </p>
      )}
      <button type="button" onClick={onStop}>
        Stop following
      </button>
    </section>
  );
}

function Standing({
  load,
  days,
  onCommand,
  onStart,
}: {
  load: PlaybackLoad;
  days: number | null;
  onCommand: (command: PlaybackCommand) => void;
  onStart: () => void;
}) {
  switch (load.status) {
    case "none":
    case "loading":
      return <p data-testid="playback-status">Asking where the run played back stands…</p>;
    case "unstarted":
      return (
        <p data-testid="playback-status">
          This scenario's run is not played back yet.{" "}
          <button type="button" onClick={onStart}>
            Play it back
          </button>
        </p>
      );
    case "unavailable":
      return (
        <p data-testid="playback-status" role="alert">
          The run played back cannot be followed: {load.reason}.
        </p>
      );
    case "loaded": {
      const { state } = load;
      const pace = state.playing ? `playing a day in ${state.secondsPerDay} s` : "paused";
      return (
        <>
          <p data-testid="playback-status">
            Following run <code>{state.runId}</code>, epoch {state.epoch}: {pace}; worked out to day{" "}
            {Math.floor(state.workedOutS / DAY_S)}.
          </p>
          <Progress state={state} days={days} />
          <p>
            <button type="button" onClick={() => onCommand(state.playing ? "pause" : "play")}>
              {state.playing ? "Pause" : "Play"}
            </button>{" "}
            <button type="button" onClick={() => onCommand("restart")}>
              Start over
            </button>
          </p>
        </>
      );
    }
  }
}

/** Where the run's clock stands across all its days, as one progress: a bar
 * from the run's start to its end, which moves only as the clock does, and
 * the moment reached, in the minute the view draws, once the run's length
 * is known. */
function Progress({ state, days }: { state: PlaybackState; days: number | null }) {
  const end = days === null ? null : days * DAY_S;
  return (
    <p className="playback-progress">
      {end !== null && (
        <progress aria-label="The run's progress" max={end} value={Math.min(state.timeS, end)} />
      )}
      <span data-testid="playback-progress">
        {describeTime(followedMoment(state))}
        {days === null ? "" : ` of ${days} ${days === 1 ? "day" : "days"}`}
      </span>
    </p>
  );
}
