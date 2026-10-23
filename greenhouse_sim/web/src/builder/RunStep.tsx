import { type FormEvent, useId, useState } from "react";

import type { RunSettings } from "./api";

/** A draft's first run's days, unless another number is entered. */
const FIRST_DAYS = 7;

/**
 * The scenario step (P12.2): when and under what weather a saved draft
 * runs, as a scenario of its own. A weather is one of the simulator's, by
 * name: synthetic or recorded, never this site's observed one.
 */
export function RunStep({
  weathers,
  disabled,
  why,
  onRun,
}: {
  weathers: readonly string[];
  disabled: boolean;
  why: string;
  onRun: (settings: RunSettings) => void;
}) {
  const heading = useId();
  const [start, setStart] = useState("2026-04-01");
  const [days, setDays] = useState(String(FIRST_DAYS));
  const [weather, setWeather] = useState(weathers[0] ?? "default");
  const [seed, setSeed] = useState("0");

  function run(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onRun({
      start_date: start,
      duration_days: Number(days),
      random_seed: Number(seed),
      weather,
    });
  }

  return (
    <form className="builder-run" aria-labelledby={heading} onSubmit={run}>
      <h2 id={heading}>Run it</h2>
      <label className="builder-field">
        <span>Starting on</span>
        <input
          type="date"
          required
          value={start}
          onChange={(event) => setStart(event.target.value)}
        />
      </label>
      <label className="builder-field">
        <span>Days</span>
        <input
          type="number"
          step={1}
          min={1}
          required
          value={days}
          onChange={(event) => setDays(event.target.value)}
        />
      </label>
      <label className="builder-field">
        <span>Weather</span>
        <select value={weather} onChange={(event) => setWeather(event.target.value)}>
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
          value={seed}
          onChange={(event) => setSeed(event.target.value)}
        />
      </label>
      {disabled && <p className="builder-note">{why}</p>}
      <button type="submit" disabled={disabled}>
        Run this revision
      </button>
    </form>
  );
}
