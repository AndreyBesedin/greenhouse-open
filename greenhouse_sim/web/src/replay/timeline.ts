import { DAY_S, runDay } from "../clock";

/**
 * What a replay's timeline covers (P17.6, decision 0065): a position is a
 * place over a stored epoch, never past what is computed. `startS` is where
 * what is kept begins (0, unless a store keeps only a window of the present),
 * `frontierS` how far it is computed, `endS` where the run ends if that is
 * known.
 */
export interface Span {
  startS: number;
  frontierS: number;
  endS: number | null;
}

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const HOURS_PER_DAY = 24;
const TWO_DIGITS = 2;
const FULL = 1;
// How many labelled ticks a timeline has at most.
const MOST_TICKS = 6;
const DAYS_PER_WEEK = 7;
const DAYS_PER_MONTH = 30;
const DAYS_PER_QUARTER = 90;
const DAYS_PER_YEAR = 365;
// The steps between ticks that read well, in days, from the finest: a day, a
// week, a fortnight, a month, two, a quarter and a year.
const TICK_STEPS_DAYS = [
  1,
  DAYS_PER_WEEK,
  2 * DAYS_PER_WEEK,
  DAYS_PER_MONTH,
  2 * DAYS_PER_MONTH,
  DAYS_PER_QUARTER,
  DAYS_PER_YEAR,
];

/** How far across the timeline a moment is, from 0 to 1. A run of no known
 * end is drawn across what is computed. */
export function fractionOf(timeS: number, span: Span): number {
  const total = extent(span);
  return total <= 0 ? 0 : Math.min(FULL, Math.max(0, (timeS - span.startS) / total));
}

/** How long the timeline's whole length is, in seconds. */
function extent(span: Span): number {
  return Math.max(span.endS ?? span.frontierS, span.frontierS) - span.startS;
}

/** The share of the timeline that is computed, from 0 to 1. */
export function computedShare(span: Span): number {
  return fractionOf(span.frontierS, span);
}

/** The moment a place across the timeline stands for, a whole minute (the
 * viewer draws whole minutes), and never past what is computed. */
export function momentAt(fraction: number, span: Span): number {
  const raw = span.startS + Math.min(FULL, Math.max(0, fraction)) * extent(span);
  return clamp(Math.round(raw / SECONDS_PER_MINUTE) * SECONDS_PER_MINUTE, span);
}

/** A moment held to the part of the run that can be played. */
export function clamp(timeS: number, span: Span): number {
  return Math.min(span.frontierS, Math.max(span.startS, timeS));
}

/** A day on, or back, at the same time of day, held to what is computed. */
export function dayAway(timeS: number, days: 1 | -1, span: Span): number {
  return clamp(timeS + days * DAY_S, span);
}

/** `Day 18, 06:00`: the run's day, counted from 1, and the time of day. A
 * day's last moment is its midnight, `Day 3, 24:00`, as the viewer has it. */
export function dayLabel(timeS: number): string {
  const day = runDay(timeS);
  const within = Math.round(timeS - day * DAY_S);
  const hours = Math.floor(within / SECONDS_PER_HOUR);
  const minutes = Math.floor((within - hours * SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  return `Day ${day + 1}, ${String(hours).padStart(TWO_DIGITS, "0")}:${String(minutes).padStart(TWO_DIGITS, "0")}`;
}

/** What a fork came from, in words. */
export function forkedText(fork: { epoch: number; at_s: number }): string {
  return `forked from epoch ${fork.epoch} at ${dayLabel(fork.at_s)}`;
}

/** How many days are computed, whole: a day counts once its last moment is. */
export function daysComputed(span: Span): number {
  return Math.floor(span.frontierS / DAY_S);
}

/** `Computed to day 41 of 120`, or without the length if it is not known. */
export function computedText(span: Span): string {
  const done = daysComputed(span);
  return span.endS === null
    ? `Computed to day ${done}`
    : `Computed to day ${done} of ${Math.round(span.endS / DAY_S)}`;
}

/** The day numbers a timeline labels, from 0, at a step that gives it about
 * as many as read well; the last is the run's end when that is a tick. */
export function dayTicks(span: Span): number[] {
  const days = Math.max(1, Math.ceil(extent(span) / DAY_S));
  const first = Math.floor(span.startS / DAY_S);
  const step = TICK_STEPS_DAYS.find((s) => days / s <= MOST_TICKS) ?? days;
  const last = first + days;
  const ticks: number[] = [];
  for (let day = Math.ceil(first / step) * step; day <= last; day += step) {
    ticks.push(day);
  }
  return ticks;
}

/** How far a key moves the handle: an arrow an hour, a page a day. */
export const KEY_STEPS_S: Readonly<Record<string, number>> = {
  ArrowLeft: -SECONDS_PER_HOUR,
  ArrowDown: -SECONDS_PER_HOUR,
  ArrowRight: SECONDS_PER_HOUR,
  ArrowUp: SECONDS_PER_HOUR,
  PageDown: -HOURS_PER_DAY * SECONDS_PER_HOUR,
  PageUp: HOURS_PER_DAY * SECONDS_PER_HOUR,
};

/** Where a key moves the handle to, or null if it is not a key it moves by. */
export function movedByKey(key: string, timeS: number, span: Span): number | null {
  if (key === "Home") {
    return span.startS;
  }
  if (key === "End") {
    return span.frontierS;
  }
  const step = KEY_STEPS_S[key];
  return step === undefined ? null : clamp(timeS + step, span);
}
