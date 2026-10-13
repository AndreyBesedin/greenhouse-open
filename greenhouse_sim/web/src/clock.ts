/**
 * A run's clock, as the simulator keeps it (`greenhouse_sim.core.clock`,
 * P09.2): its moments are seconds from its start, its start date's midnight
 * at its site, and its days are that clock's days.
 *
 * A moment belongs to the day it lies in, or, at a midnight, to the day it
 * ends: 86 400 s is still day 0, the end of its first day. So a later day
 * runs from just after its midnight to the next, inclusive.
 */

export const DAY_S = 86_400;

/** The day of a run a moment belongs to: the one it lies in, or ends. */
export function runDay(seconds: number): number {
  return Math.max(0, Math.ceil(seconds / DAY_S) - 1);
}

/** When the day a moment belongs to began, in seconds from the run's start. */
export function dayStart(seconds: number): number {
  return runDay(seconds) * DAY_S;
}

/** When the day a moment belongs to ends: the last moment that is still
 * that day's. */
export function dayEnd(seconds: number): number {
  return dayStart(seconds) + DAY_S;
}
