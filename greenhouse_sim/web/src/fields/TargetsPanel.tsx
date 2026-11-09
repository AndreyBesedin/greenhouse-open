import { useState } from "react";

import { useFolds } from "../folds";
import { formatValue } from "../readouts";
import { useForkQuestion } from "../replay/useForkQuestion";
import type { ThermostatAt } from "../scene/equipment";
import { describeTime } from "./ClimateTime";

// What a target change sets, as the simulator names it (#274).
export const HEATING_DAY = "heating_day";
export const HEATING_NIGHT = "heating_night";
// The heating setpoints the simulator takes, in °C, and the step the inputs
// move by.
const LOWEST_C = 0;
const HIGHEST_C = 40;
const STEP_C = 0.5;
// A target changes on the minute (#274).
const MINUTE_S = 60;

/** The heating targets in a line, as their section folded says how they
 * stand: the setpoints in force at the moment drawn. */
export function describeTargets(thermostat: ThermostatAt | null): string {
  return thermostat === null
    ? "Heating targets"
    : `Heating targets: ${formatValue(thermostat.dayC)} °C by day, ${formatValue(thermostat.nightC)} °C by night`;
}

/** The moment a target set now takes effect: the moment drawn, or the next
 * minute if it lies between two. */
export function settingMoment(time: number): number {
  return Math.ceil(time / MINUTE_S) * MINUTE_S;
}

/**
 * The run's heating targets (#274): its thermostat's setpoints by day and by
 * night, as in force at the moment drawn, and changed from then on. A change
 * is a target change in the address at the moment drawn, the next minute if
 * it lies between two; an epoch a replay shows while it is computed is given
 * it through its changes, from its next minute (P22.1, decision 0073).
 */
export function TargetsPanel({
  thermostat,
  time,
  followed,
  forking = false,
  noFork = null,
  forkFrom = null,
  onSet,
}: {
  /** The thermostat at the moment drawn, with its setpoints then; null
   * while they are not known. */
  thermostat: ThermostatAt | null;
  /** The moment drawn, in seconds into the run. */
  time: number;
  /** Whether a change steers the run as it is computed, from its next
   * minute: the epoch a replay shows while it is computed. */
  followed: boolean;
  /** Whether setting them makes a fork of a stored run, which stays as it was. */
  forking?: boolean;
  /** Why no fork can be made at the moment drawn, if none can. */
  noFork?: string | null;
  /** The moment the fork takes, if the transport reads another. */
  forkFrom?: string | null;
  /** Sets the targets changed, by name, in °C. */
  onSet: (targets: Record<string, number>) => void;
}) {
  const fold = useFolds<"targets">();
  return (
    <details className="targets-fold" {...fold("targets")}>
      <summary data-testid="targets-summary">{describeTargets(thermostat)}</summary>
      {thermostat === null ? (
        <p className="targets-note">The run's setpoints are on their way.</p>
      ) : (
        // Keyed by the setpoints in force, so that the inputs start from them
        // again once the run or its moment changes them.
        <TargetsForm
          key={`${thermostat.dayC}/${thermostat.nightC}`}
          thermostat={thermostat}
          time={time}
          followed={followed}
          forking={forking}
          noFork={noFork}
          forkFrom={forkFrom}
          onSet={onSet}
        />
      )}
    </details>
  );
}

function TargetsForm({
  thermostat,
  time,
  followed,
  forking,
  noFork,
  forkFrom,
  onSet,
}: {
  thermostat: ThermostatAt;
  time: number;
  followed: boolean;
  forking: boolean;
  noFork: string | null;
  forkFrom: string | null;
  onSet: (targets: Record<string, number>) => void;
}) {
  const [day, setDay] = useState(String(thermostat.dayC));
  const [night, setNight] = useState(String(thermostat.nightC));
  const changed: Record<string, number> = {};
  for (const [target, given, now] of [
    [HEATING_DAY, day, thermostat.dayC],
    [HEATING_NIGHT, night, thermostat.nightC],
  ] as const) {
    const value = Number(given);
    if (given !== "" && Number.isFinite(value) && value !== now) {
      changed[target] = value;
    }
  }
  const valid = [day, night].every((given) => {
    const value = Number(given);
    return given !== "" && value >= LOWEST_C && value <= HIGHEST_C;
  });
  const { trigger, ask, question } = useForkQuestion({ about: JSON.stringify(changed) });
  const from = forking
    ? `in a fork of this run, from ${forkFrom ?? "its next minute"}`
    : followed
      ? "from the run's next minute"
      : `from ${describeTime(settingMoment(time))}`;
  return (
    <form
      className="targets-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (forking) {
          ask(() => onSet(changed));
        } else {
          onSet(changed);
        }
      }}
    >
      <label>
        By day, °C{" "}
        <input
          type="number"
          min={LOWEST_C}
          max={HIGHEST_C}
          step={STEP_C}
          value={day}
          onChange={(event) => setDay(event.target.value)}
        />
      </label>{" "}
      <label>
        By night, °C{" "}
        <input
          type="number"
          min={LOWEST_C}
          max={HIGHEST_C}
          step={STEP_C}
          value={night}
          onChange={(event) => setNight(event.target.value)}
        />
      </label>{" "}
      <button
        ref={trigger}
        type="submit"
        disabled={!valid || Object.keys(changed).length === 0 || noFork !== null}
      >
        Set {from}
      </button>
      {noFork !== null && <p className="targets-note">{noFork}</p>}
      {question}
    </form>
  );
}
