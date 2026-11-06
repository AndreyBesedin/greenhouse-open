import { type StoredRun, sizeText } from "./storedRuns";

/** What is said of a figure no worker of the run's own measured: a run computed
 * in the API's process, or kept from before runs said what they used. None is
 * not zero. */
export const NOT_MEASURED = "not measured";

/** Why a figure is not measured, said where it is. */
export const NOT_MEASURED_NOTE =
  "No worker of this run's own measured it: a run computed in the simulator's own process, or kept from before runs said what they used, has no figure, which is not zero.";

const MINUTE_S = 60;
const HOUR_S = 60 * MINUTE_S;
// Under this many seconds, a tenth of one says something.
const TENTHS_UNDER_S = 10;
const TENTHS = 10;

/** A length of time as a person reads it: "4.2 s", "42 s", "22 min 37 s",
 * "3 h 5 min". */
export function durationText(seconds: number): string {
  const tenths = Math.round(seconds * TENTHS) / TENTHS;
  if (tenths < TENTHS_UNDER_S) {
    return `${tenths.toFixed(1)} s`;
  }
  const whole = Math.round(seconds);
  if (whole < MINUTE_S) {
    return `${whole} s`;
  }
  if (whole < HOUR_S) {
    const left = whole % MINUTE_S;
    return left === 0
      ? `${Math.floor(whole / MINUTE_S)} min`
      : `${Math.floor(whole / MINUTE_S)} min ${left} s`;
  }
  const minutes = Math.floor((whole % HOUR_S) / MINUTE_S);
  const hours = Math.floor(whole / HOUR_S);
  return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`;
}

/** Simulated days, in words, to a tenth of one: "1 day", "120 days", "2.5 days". */
export function daysText(days: number): string {
  const tenths = Math.round(days * TENTHS) / TENTHS;
  const shown = Number.isInteger(tenths) ? String(tenths) : tenths.toFixed(1);
  return shown === "1" ? "1 day" : `${shown} days`;
}

/** One figure of what a run used: what it is, its value in words, and whether a
 * worker measured it. */
export interface UsageFigure {
  label: string;
  value: string;
  measured: boolean;
}

function measuredOr<T>(value: T | null, inWords: (value: T) => string): [string, boolean] {
  return value === null ? [NOT_MEASURED, false] : [inWords(value), true];
}

/** What a run has used, as its report says (decision 0067): what it keeps, the
 * days it computed itself, and, of its workers, the seconds of a core, the most
 * memory one held and their time from each start. */
export function usageFigures(run: StoredRun): UsageFigure[] {
  const [cpu, cpuMeasured] = measuredOr(run.cpu_s, durationText);
  const [memory, memoryMeasured] = measuredOr(run.peak_memory_bytes, sizeText);
  const [wall, wallMeasured] = measuredOr(run.wall_s, durationText);
  return [
    { label: "Kept", value: sizeText(run.size_bytes), measured: true },
    { label: "Computed", value: daysText(run.days_computed), measured: true },
    { label: "CPU", value: cpu, measured: cpuMeasured },
    { label: "Peak memory", value: memory, measured: memoryMeasured },
    { label: "Wall time", value: wall, measured: wallMeasured },
  ];
}
