import { type FormEvent, useId } from "react";

import { Button } from "../design/Button";
import { Field } from "../design/Field";
import { Notice } from "../design/Notice";
import { weatherName } from "../weather/WeatherPanel";
import type { RunSettings } from "./api";
import { describedBy, type Reasons, WhyNot } from "./WhyNot";

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
 * name: synthetic or recorded, never this site's observed one. Below its
 * button, why it cannot run now, each reason in full, and why the simulator
 * refused the last run asked for.
 */
export function RunStep({
  weathers,
  busy,
  reasons,
  refused,
  fields,
  onFields,
  onRun,
}: {
  weathers: readonly string[];
  busy: boolean;
  /** Why the revision cannot run now, or none. */
  reasons: Reasons;
  /** Why the simulator refused the last run asked for here, if it did. */
  refused?: string | undefined;
  fields: RunFields;
  onFields: (fields: RunFields) => void;
  onRun: (settings: RunSettings) => void;
}) {
  const heading = useId();
  const why = useId();
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
      {/* Each label over its control, a row of them wrapped to the column's width, so
          that a date shows whole (the QA of 2026-11-04). */}
      <div className="builder-give">
        <Field label="Starting on" size="compact" className="builder-give-field">
          {(control) => (
            <input
              {...control}
              type="date"
              required
              value={fields.start}
              onChange={(event) => set({ start: event.target.value })}
            />
          )}
        </Field>
        <Field label="Days" size="compact" className="builder-give-field">
          {(control) => (
            <input
              {...control}
              type="number"
              step={1}
              min={1}
              required
              value={fields.days}
              onChange={(event) => set({ days: event.target.value })}
            />
          )}
        </Field>
        <Field label="Weather" size="compact" className="builder-give-field">
          {(control) => (
            <select
              {...control}
              value={fields.weather}
              onChange={(event) => set({ weather: event.target.value })}
            >
              {(weathers.length > 0 ? weathers : ["default"]).map((each) => (
                <option key={each} value={each}>
                  {weatherName(each)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Seed" size="compact" className="builder-give-field">
          {(control) => (
            <input
              {...control}
              type="number"
              step={1}
              min={0}
              required
              value={fields.seed}
              onChange={(event) => set({ seed: event.target.value })}
            />
          )}
        </Field>
      </div>
      <Button
        type="submit"
        size="compact"
        disabled={busy || reasons.length > 0}
        aria-describedby={describedBy(why, reasons)}
      >
        Run this revision
      </Button>
      <WhyNot id={why} lead="It cannot run:" reasons={reasons} testId="builder-run-why" />
      {refused !== undefined && (
        <Notice kind="problem" className="builder-refused" data-testid="builder-run-refused">
          It does not run: {refused}
        </Notice>
      )}
    </form>
  );
}
