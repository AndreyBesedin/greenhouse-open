import { useEffect, useState } from "react";

import { DAY_S, dayStart, runDay } from "../clock";

// The time of day moves a minute at a time.
export const CLIMATE_STEP_S = 60;
// Playing moves a minute at a time through the first hour, and five minutes
// at a time after it, so that a day plays in a few minutes.
export const PLAY_LATER_STEP_S = 300;
const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const MINUTE_DIGITS = 2;
// Playing, the run moves on a step this long after each moment arrives.
const PLAY_PAUSE_MS = 400;
const MS_PER_S = 1000;
/** How far each step of play moves, to choose from: the first, a day in a
 * few minutes; the last, the same time of day, day after day. */
export const PACES: readonly { stepS: number; label: string }[] = [
  { stepS: PLAY_LATER_STEP_S, label: "5 min a step" },
  { stepS: SECONDS_PER_HOUR, label: "1 h a step" },
  { stepS: DAY_S, label: "1 day a step" },
];

/** A moment of a climate run, as the viewer writes it: `10 min` in its
 * first hour, `5 h 05 min` after it, and, on a later day, its day before
 * them (`day 3, 5 h 05 min`). A day's last moment is its midnight, `24 h
 * 00 min` (`../clock`). */
export function describeTime(seconds: number): string {
  const day = runDay(seconds);
  const within = seconds - dayStart(seconds);
  let said: string;
  if (within < SECONDS_PER_HOUR) {
    said = `${Math.round((within / SECONDS_PER_MINUTE) * 10) / 10} min`;
  } else {
    const hours = Math.floor(within / SECONDS_PER_HOUR);
    const minutes = Math.round((within - hours * SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
    said = `${hours} h ${String(minutes).padStart(MINUTE_DIGITS, "0")} min`;
  }
  return day === 0 ? said : `day ${day}, ${said}`;
}

/** A climate run's moment in a line, as its section folded says it (#273):
 * the moment drawn, as `ClimateTime` shows it, and the one asked for while
 * it is on its way or cannot be drawn, so that the line never takes a
 * moment still loading, or one that failed, for the one in the view. */
export function describeClimateRun(time: number, shown: number | null, failed: boolean): string {
  if (shown === time) {
    return `Climate run: ${describeTime(time)}`;
  }
  const drawn = shown === null ? "" : `${describeTime(shown)}; `;
  return failed
    ? `Climate run: ${drawn}${describeTime(time)} cannot be drawn`
    : `Climate run: ${drawn}loading ${describeTime(time)}…`;
}

/** How far play moves on from a moment, at a pace (`PACES`): at the first,
 * a minute at a time through the run's first hour. */
export function playStep(seconds: number, paceS: number = PLAY_LATER_STEP_S): number {
  return paceS === PLAY_LATER_STEP_S && seconds < SECONDS_PER_HOUR ? CLIMATE_STEP_S : paceS;
}

/** The moment at a time of day on another day of a run. A later day begins
 * a minute after its midnight, which is the day before's end. */
export function onDay(day: number, withinS: number): number {
  const earliest = day === 0 ? 0 : CLIMATE_STEP_S;
  return day * DAY_S + Math.min(DAY_S, Math.max(earliest, withinS));
}

/** How many whole seconds `asked` has waited, counted afresh whenever it
 * changes, and second by second while `waiting`. */
function useSecondsWaited(asked: number, waiting: boolean): number {
  const [since, setSince] = useState<{ asked: number; at: number }>(() => ({
    asked,
    at: Date.now(),
  }));
  const [now, setNow] = useState(since.at);
  if (since.asked !== asked) {
    const at = Date.now();
    setSince({ asked, at });
    setNow(at);
  }
  useEffect(() => {
    if (!waiting) {
      return;
    }
    const tick = setInterval(() => setNow(Date.now()), MS_PER_S);
    return () => clearInterval(tick);
  }, [waiting]);
  return Math.floor((now - since.at) / MS_PER_S);
}

/** `text`, its first letter a capital, to begin a sentence. */
function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * How far into its climate run a scenario's climate is drawn: a slider over
 * the moment's day, a minute at a time; through a run of several days, a
 * slider over its days, with a step either way; and play, which moves on
 * once the last moment asked for has arrived (`playStep`), at the pace
 * chosen, until the run's end. The moment shown is the one drawn; while
 * another is on its way, it says which and for how long, so that a slow
 * step is never taken for one that does nothing (#198, #202). A moment
 * that cannot be drawn stops play.
 *
 * Followed, the run played back moves the moment on with its clock
 * (decision 0041), and its own play and pause are the view's: the climate
 * run's play, sliders, day steps and pace stand aside, and say so, so that
 * none shows a state the run is not in (#270).
 */
export function ClimateTime({
  time,
  shown,
  failed = false,
  followed = false,
  days,
  playing,
  onTime,
  onPlaying,
}: {
  /** The moment asked for, in seconds. */
  time: number;
  /** The moment of the field drawn, once one has arrived. */
  shown: number | null;
  /** Whether the moment asked for cannot be drawn, which the scene's status
   * says why. */
  failed?: boolean;
  /** Whether the view follows the run played back, whose clock then moves
   * the moment on in place of this play. */
  followed?: boolean;
  /** How many days the run lasts. */
  days: number;
  playing: boolean;
  onTime: (seconds: number) => void;
  onPlaying: (playing: boolean) => void;
}) {
  const [pace, setPace] = useState(PLAY_LATER_STEP_S);
  const end = days * DAY_S;
  const arrived = shown === time;
  const waiting = !arrived && !failed;
  const waited = useSecondsWaited(time, waiting);
  // Play stops at a moment that cannot be drawn, and once the view follows
  // the run played back: two plays would move the moment on at once.
  useEffect(() => {
    if (playing && (failed || followed)) {
      onPlaying(false);
    }
  }, [playing, failed, followed, onPlaying]);
  useEffect(() => {
    if (!playing || !arrived || followed) {
      return;
    }
    if (time >= end) {
      onPlaying(false);
      return;
    }
    const next = setTimeout(
      () => onTime(Math.min(time + playStep(time, pace), end)),
      PLAY_PAUSE_MS,
    );
    return () => clearTimeout(next);
  }, [playing, arrived, followed, time, end, pace, onTime, onPlaying]);

  const day = runDay(time);
  const within = time - dayStart(time);
  return (
    <fieldset className="climate-time" aria-label="Climate run">
      <div className="climate-time-row">
        {!followed && (
          <>
            <button type="button" onClick={() => onPlaying(!playing)}>
              {playing ? "Pause" : "Play"}
            </button>
            <input
              className="climate-time-slider"
              type="range"
              aria-label="Time of day"
              min={day === 0 ? 0 : CLIMATE_STEP_S}
              max={DAY_S}
              step={CLIMATE_STEP_S}
              value={within}
              onChange={(event) => onTime(onDay(day, Number(event.target.value)))}
            />
          </>
        )}
        <span data-testid="climate-time">{describeTime(shown ?? time)}</span>
      </div>
      {followed && (
        <p className="climate-time-note" data-testid="climate-followed">
          The run played back moves this moment on with its clock: play and pause it there. Stop
          following to choose the moment here, or play it.
        </p>
      )}
      {waiting && (
        <p className="climate-time-note" data-testid="climate-pending">
          {playing ? "Playing: waiting for" : "Loading"} {describeTime(time)}… {waited} s
        </p>
      )}
      {failed && !arrived && (
        <p className="climate-time-note" data-testid="climate-failed" role="alert">
          {sentence(describeTime(time))} cannot be drawn
          {shown === null ? "" : `; ${describeTime(shown)} is shown`}.
        </p>
      )}
      {days > 1 && !followed && (
        <div className="climate-time-row">
          <button
            type="button"
            aria-label="Previous day"
            disabled={day === 0}
            onClick={() => onTime(onDay(day - 1, within))}
          >
            ◀
          </button>
          <input
            className="climate-time-slider"
            type="range"
            aria-label="Day of the run"
            min={0}
            max={days - 1}
            step={1}
            value={day}
            onChange={(event) => onTime(onDay(Number(event.target.value), within))}
          />
          <button
            type="button"
            aria-label="Next day"
            disabled={day >= days - 1}
            onClick={() => onTime(onDay(day + 1, within))}
          >
            ▶
          </button>
          <select
            aria-label="Pace"
            value={pace}
            onChange={(event) => setPace(Number(event.target.value))}
          >
            {PACES.map(({ stepS, label }) => (
              <option key={stepS} value={stepS}>
                {label}
              </option>
            ))}
          </select>
        </div>
      )}
    </fieldset>
  );
}
