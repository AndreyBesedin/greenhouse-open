import { useEffect } from "react";

import { CLIMATE_RUN_S } from "./source";

// The slider moves a minute at a time.
export const CLIMATE_STEP_S = 60;
// Playing moves a minute at a time through the first hour, and five minutes
// at a time after it, so that a day plays in a few minutes.
export const PLAY_LATER_STEP_S = 300;
const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const MINUTE_DIGITS = 2;
// Playing, the run moves on a step this long after each moment arrives.
const PLAY_PAUSE_MS = 400;

/** A moment of a climate run, as the viewer writes it: `10 min` in its
 * first hour, `5 h 05 min` after it. */
export function describeTime(seconds: number): string {
  if (seconds < SECONDS_PER_HOUR) {
    return `${Math.round((seconds / SECONDS_PER_MINUTE) * 10) / 10} min`;
  }
  const hours = Math.floor(seconds / SECONDS_PER_HOUR);
  const minutes = Math.round((seconds - hours * SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  return `${hours} h ${String(minutes).padStart(MINUTE_DIGITS, "0")} min`;
}

/** How far play moves on from a moment. */
export function playStep(seconds: number): number {
  return seconds < SECONDS_PER_HOUR ? CLIMATE_STEP_S : PLAY_LATER_STEP_S;
}

/**
 * How far into its climate run a scenario's climate is drawn: a slider over
 * the run's day, a minute at a time, and play, which moves on once the last
 * moment asked for has arrived (`playStep`), until the run's end.
 */
export function ClimateTime({
  time,
  shown,
  playing,
  onTime,
  onPlaying,
}: {
  /** The moment asked for, in seconds. */
  time: number;
  /** The moment of the field drawn, once it has arrived. */
  shown: number | null;
  playing: boolean;
  onTime: (seconds: number) => void;
  onPlaying: (playing: boolean) => void;
}) {
  const arrived = shown === time;
  useEffect(() => {
    if (!playing || !arrived) {
      return;
    }
    if (time >= CLIMATE_RUN_S) {
      onPlaying(false);
      return;
    }
    const next = setTimeout(
      () => onTime(Math.min(time + playStep(time), CLIMATE_RUN_S)),
      PLAY_PAUSE_MS,
    );
    return () => clearTimeout(next);
  }, [playing, arrived, time, onTime, onPlaying]);

  return (
    <fieldset className="climate-time" aria-label="Climate run">
      <button type="button" onClick={() => onPlaying(!playing)}>
        {playing ? "Pause" : "Play"}
      </button>
      <input
        className="climate-time-slider"
        type="range"
        aria-label="Time into the run"
        min={0}
        max={CLIMATE_RUN_S}
        step={CLIMATE_STEP_S}
        value={time}
        onChange={(event) => onTime(Number(event.target.value))}
      />
      <span data-testid="climate-time">{describeTime(shown ?? time)}</span>
    </fieldset>
  );
}
