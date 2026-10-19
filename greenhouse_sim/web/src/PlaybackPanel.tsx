import { DAY_S } from "./clock";
import { describeTime } from "./fields/ClimateTime";
import type { PlaybackCommand, PlaybackLoad } from "./scene/playback";

/**
 * The run a view follows as it is played back (P10.2, decision 0041): which
 * run, its epoch, where its clock stands and how fast it plays, with its
 * controls, which every viewer and consumer of it shares. The view draws the
 * run at that clock's moment; a change made here (a command, a weather, an
 * opening) makes another run, which the view then draws in its place, and
 * says so.
 */
export function PlaybackPanel({
  load,
  changed,
  onCommand,
  onStart,
  onOwnRun,
  onStop,
}: {
  load: PlaybackLoad;
  /** What the view changes of the scenario's own run, if anything. */
  changed: readonly string[];
  onCommand: (command: PlaybackCommand) => void;
  onStart: () => void;
  /** Draws the run played back again, without the view's changes. */
  onOwnRun: () => void;
  onStop: () => void;
}) {
  return (
    <section className="playback" aria-label="Run played back">
      <Standing load={load} onCommand={onCommand} onStart={onStart} />
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
  onCommand,
  onStart,
}: {
  load: PlaybackLoad;
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
            Following run <code>{state.runId}</code>, epoch {state.epoch}:{" "}
            {describeTime(state.timeS)}, {pace}; worked out to day{" "}
            {Math.floor(state.workedOutS / DAY_S)}.
          </p>
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
