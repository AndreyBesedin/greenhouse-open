import { type FormEvent, useId } from "react";

import type { RunSettings } from "./api";

/** A draft's first run's days, unless another number is entered. */
const FIRST_DAYS = 7;

/** What the run step's fields hold, as typed. The builder keeps them while a
 * draft is shown (P17.11), and a scenario file opens with its own. */
export interface RunFields {
  start: string;
  days: string;
  weather: string;
  seed: string;
}

/** The fields of a draft's first run. */
export const FIRST_RUN: RunFields = {
  start: "2026-04-01",
  days: String(FIRST_DAYS),
  weather: "default",
  seed: "0",
};

/** The settings the fields hold, or none if they do not hold a run: a date,
 * a whole number of days of one or more, a whole seed of 0 or more. */
export function settingsOf(fields: RunFields): RunSettings | null {
  const days = Number(fields.days);
  const seed = Number(fields.seed);
  if (fields.start === "" || !Number.isInteger(days) || days < 1) {
    return null;
  }
  if (fields.seed === "" || !Number.isInteger(seed) || seed < 0) {
    return null;
  }
  return {
    start_date: fields.start,
    duration_days: days,
    random_seed: seed,
    weather: fields.weather,
  };
}

/**
 * The scenario step (P12.2): when and under what weather a saved draft
 * runs, as a scenario of its own. A weather is one of the simulator's, by
 * name: synthetic or recorded, never this site's observed one.
 */
export function RunStep({
  weathers,
  disabled,
  why,
  fields,
  onFields,
  onRun,
}: {
  weathers: readonly string[];
  disabled: boolean;
  why: string;
  fields: RunFields;
  onFields: (fields: RunFields) => void;
  onRun: (settings: RunSettings) => void;
}) {
  const heading = useId();
  const set = (change: Partial<RunFields>) => onFields({ ...fields, ...change });

  function run(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const settings = settingsOf(fields);
    if (settings !== null) {
      onRun(settings);
    }
  }

  return (
    <form className="builder-run" aria-labelledby={heading} onSubmit={run}>
      <h2 id={heading}>Run it</h2>
      <label className="builder-field">
        <span>Starting on</span>
        <input
          type="date"
          required
          value={fields.start}
          onChange={(event) => set({ start: event.target.value })}
        />
      </label>
      <label className="builder-field">
        <span>Days</span>
        <input
          type="number"
          step={1}
          min={1}
          required
          value={fields.days}
          onChange={(event) => set({ days: event.target.value })}
        />
      </label>
      <label className="builder-field">
        <span>Weather</span>
        <select value={fields.weather} onChange={(event) => set({ weather: event.target.value })}>
          {(weathers.length > 0 ? weathers : ["default"]).map((each) => (
            <option key={each} value={each}>
              {each}
            </option>
          ))}
        </select>
      </label>
      <label className="builder-field">
        <span>Seed</span>
        <input
          type="number"
          step={1}
          min={0}
          value={fields.seed}
          onChange={(event) => set({ seed: event.target.value })}
        />
      </label>
      {disabled && <p className="builder-note">{why}</p>}
      <button type="submit" disabled={disabled}>
        Run this revision
      </button>
    </form>
  );
}
