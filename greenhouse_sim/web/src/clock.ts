/**
 * A run's clock, as the simulator keeps it (`greenhouse_sim.core.clock`,
 * P09.2): its moments are seconds from its start, its start date's midnight
 * at its site, and its days are that clock's days.
 *
 * A moment belongs to the day it lies in, or, at a midnight, to the day it
 * ends: 86 400 s is still day 0, the end of its first day. So a later day
 * runs from just after its midnight to the next, inclusive. Its crop lives
 * each day at the midnight that ends it, so by 86 400 s it has lived one.
 *
 * The viewer says one thing for one day, by one rule. A moment's day is
 * named, counted from 1: "day 87" (`dayNumber`, `dayBegun`), as a replay's
 * timeline and every panel write a moment. A count of days, elapsed or
 * lived, is said as a count: "86 days in", "after 86 days" (`dayCount`),
 * never "day 86", which would name another day. Noon on the run's 87th day
 * is "day 87, 12 h 00 min", and its crop, a scene of it, is 86 days in.
 */

export const DAY_S = 86_400;

/** The day of a run a moment belongs to: the one it lies in, or ends. */
export function runDay(seconds: number): number {
  return Math.max(0, Math.ceil(seconds / DAY_S) - 1);
}

/** The day a moment belongs to as a person counts it, from 1: the run's
 * first day is day 1. Every moment the viewer writes, in a replay's timeline
 * and in every panel, is numbered so, that one page never says two day
 * numbers for one moment. */
export function dayNumber(seconds: number): number {
  return runDay(seconds) + 1;
}

/** The day that begins once `ended` days have ended, counted from 1 as
 * `dayNumber` counts it: a checkpoint of a day's start, kept with the days
 * ended before it, is named by it. */
export function dayBegun(ended: number): number {
  return ended + 1;
}

/** A count of days as a person says it, "1 day" or "86 days": what a
 * count of days elapsed or lived is written with, so that it is never read
 * as the name of a day. */
export function dayCount(count: number): string {
  return count === 1 ? "1 day" : `${count} days`;
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

/** How many of a run's days have ended by a moment, at it or before: the
 * days its crop has lived. */
export function daysEnded(seconds: number): number {
  return Math.floor(seconds / DAY_S);
}
