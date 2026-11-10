import { useEffect, useState } from "react";

import { DAY_S, dayNumber, dayStart, runDay } from "../clock";
import { Button } from "../design/Button";
import { Notice } from "../design/Notice";

// The time of day moves a minute at a time.
const CLIMATE_STEP_S = 60;
const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const MINUTE_DIGITS = 2;
const MS_PER_S = 1000;

/** A moment of a climate run, as the viewer writes it: `10 min` in its
 * first hour, `5 h 05 min` after it, and, on a later day, its day before
 * them, counted from 1 as a replay's timeline counts it: `day 4, 5 h 05 min`
 * is its `Day 4, 05:05` (`dayNumber`). A day's last moment is its midnight,
 * `24 h 00 min` (`../clock`). */
export function describeTime(seconds: number): string {
  const day = dayNumber(seconds);
  const within = seconds - dayStart(seconds);
  let said: string;
  if (within < SECONDS_PER_HOUR) {
    said = `${Math.round((within / SECONDS_PER_MINUTE) * 10) / 10} min`;
  } else {
    const hours = Math.floor(within / SECONDS_PER_HOUR);
    const minutes = Math.round((within - hours * SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
    said = `${hours} h ${String(minutes).padStart(MINUTE_DIGITS, "0")} min`;
  }
  return day === 1 ? said : `day ${day}, ${said}`;
}

/** A climate run's moment in a line, as its section folded says it (#273):
 * the moment drawn, as `ClimateTime` shows it, and the one asked for while
 * it is on its way or cannot be drawn, so that the line never takes a
 * moment still loading, or one that failed, for the one in the view. */
export function describeClimateRun(
  time: number,
  shown: number | null,
  failed: boolean,
  describe: (seconds: number) => string = describeTime,
): string {
  if (shown === time) {
    return `Climate run: ${describe(time)}`;
  }
  const drawn = shown === null ? "" : `${describe(shown)}; `;
  return failed
    ? `Climate run: ${drawn}${describe(time)} cannot be drawn`
    : `Climate run: ${drawn}loading ${describe(time)}…`;
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

/** What a replay says there: the timeline under the view moves the moment. */
export const REPLAYED_NOTE = "The replay's timeline under the view moves this moment.";

/**
 * How far into its climate run a scenario's climate is drawn: a slider over
 * the moment's day, a minute at a time, and, through a run of several days,
 * a slider over its days, with a step either way. It has no play of its
 * own: a run computed and kept is watched in a replay (decision 0074). The
 * moment shown is the one drawn; while another is on its way, it says which
 * and for how long, so that a slow step is never taken for one that does
 * nothing (#198, #202).
 *
 * Followed, as a replay's timeline moves the moment on (P17.6), the climate
 * run's sliders and day steps stand aside, and say so, so that none shows a
 * state the run is not in (#270).
 */
export function ClimateTime({
  time,
  shown,
  failed = false,
  followed = false,
  followedNote = REPLAYED_NOTE,
  describe = describeTime,
  days,
  onTime,
}: {
  /** The moment asked for, in seconds. */
  time: number;
  /** The moment of the field drawn, once one has arrived. */
  shown: number | null;
  /** Whether the moment asked for cannot be drawn, which the scene's status
   * says why. */
  failed?: boolean;
  /** Whether something else moves the moment on: a replay's timeline. */
  followed?: boolean;
  /** What is said in place of this moment's controls, when it is followed. */
  followedNote?: string;
  /** The words a moment is said in: a replay's are its timeline's. */
  describe?: (seconds: number) => string;
  /** How many days the run lasts. */
  days: number;
  onTime: (seconds: number) => void;
}) {
  const arrived = shown === time;
  const waiting = !arrived && !failed;
  const waited = useSecondsWaited(time, waiting);

  const day = runDay(time);
  const within = time - dayStart(time);
  return (
    <fieldset className="climate-time" aria-label="Climate run">
      <div className="climate-time-row">
        {!followed && (
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
        )}
        <span data-testid="climate-time">{describe(shown ?? time)}</span>
      </div>
      {followed && (
        <p className="climate-time-note" data-testid="climate-followed">
          {followedNote}
        </p>
      )}
      {/* While the view follows a replay, the line keeps its place between
          one moment's loading and the next's, so that the rows below stay
          where they are (#301); only its words are shown or not. */}
      {(waiting || (followed && !failed)) && (
        <p
          className={waiting ? "climate-time-note" : "climate-time-note climate-time-idle"}
          data-testid={waiting ? "climate-pending" : undefined}
          aria-hidden={waiting ? undefined : true}
        >
          Loading {describe(time)}… {waited} s
        </p>
      )}
      {failed && !arrived && (
        <Notice kind="problem" className="climate-time-note" data-testid="climate-failed">
          {sentence(describe(time))} cannot be drawn
          {shown === null ? "" : `; ${describe(shown)} is shown`}.
        </Notice>
      )}
      {days > 1 && !followed && (
        <div className="climate-time-row">
          <Button
            size="compact"
            aria-label="Previous day"
            disabled={day === 0}
            onClick={() => onTime(onDay(day - 1, within))}
          >
            ◀
          </Button>
          <input
            className="climate-time-slider"
            type="range"
            aria-label="Day of the run"
            min={0}
            max={days - 1}
            step={1}
            value={day}
            aria-valuetext={`day ${dayNumber(time)}`}
            onChange={(event) => onTime(onDay(Number(event.target.value), within))}
          />
          <Button
            size="compact"
            aria-label="Next day"
            disabled={day >= days - 1}
            onClick={() => onTime(onDay(day + 1, within))}
          >
            ▶
          </Button>
        </div>
      )}
    </fieldset>
  );
}
