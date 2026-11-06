import { describe, expect, it } from "vitest";

import { DAY_S, dayBegun, dayEnd, dayNumber, dayStart, daysEnded, runDay } from "./clock";

describe("a run's clock", () => {
  it.each([
    [0, 0],
    [1, 0],
    [DAY_S, 0],
    [DAY_S + 1, 1],
    [2 * DAY_S, 1],
    [2 * DAY_S + 0.5, 2],
  ])("puts %d s in the day it lies in, or ends: day %d", (seconds, day) => {
    expect(runDay(seconds)).toBe(day);
    expect(dayStart(seconds)).toBe(day * DAY_S);
    expect(dayEnd(seconds)).toBe((day + 1) * DAY_S);
  });

  it.each([
    [0, 0],
    [DAY_S - 1, 0],
    [DAY_S, 1],
    [2.5 * DAY_S, 2],
  ])("has the crop live a day at each midnight: by %d s, %d", (seconds, days) => {
    expect(daysEnded(seconds)).toBe(days);
  });

  it("counts its days from 1 to a person, and names a day's start by the day it begins", () => {
    expect(dayNumber(0)).toBe(1);
    expect(dayNumber(DAY_S)).toBe(1);
    expect(dayNumber(DAY_S + 1)).toBe(2);
    expect(dayNumber(3.5 * DAY_S)).toBe(4);
    // The start of the run's second day, once one day has ended.
    expect(dayBegun(daysEnded(DAY_S))).toBe(2);
    expect(dayBegun(daysEnded(DAY_S))).toBe(dayNumber(DAY_S + 1));
  });
});
