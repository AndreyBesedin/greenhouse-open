import { describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import {
  clamp,
  computedShare,
  computedText,
  dayAway,
  dayLabel,
  dayTicks,
  forkedText,
  fractionOf,
  momentAt,
  movedByKey,
  type Span,
} from "./timeline";

const RUN: Span = { startS: 0, frontierS: 41 * DAY_S, endS: 120 * DAY_S };

describe("the timeline's reach", () => {
  it("is drawn across the whole run, and computed to the frontier", () => {
    expect(fractionOf(30 * DAY_S, RUN)).toBeCloseTo(0.25);
    expect(computedShare(RUN)).toBeCloseTo(41 / 120);
  });

  it("is drawn across what is computed when the end is not known", () => {
    expect(computedShare({ startS: 0, frontierS: 5 * DAY_S, endS: null })).toBe(1);
  });

  it("starts at what is kept, not at the run's start", () => {
    const window: Span = { startS: 10 * DAY_S, frontierS: 14 * DAY_S, endS: null };
    expect(fractionOf(12 * DAY_S, window)).toBeCloseTo(0.5);
    expect(momentAt(0, window)).toBe(10 * DAY_S);
  });
});

describe("a place across the timeline", () => {
  it("is a whole minute", () => {
    expect(momentAt(0.1234, RUN) % 60).toBe(0);
  });

  it("is never past what is computed", () => {
    expect(momentAt(1, RUN)).toBe(41 * DAY_S);
    expect(momentAt(0.9, RUN)).toBe(41 * DAY_S);
    expect(momentAt(-1, RUN)).toBe(0);
  });

  it("holds any moment to the part of the run that can be played", () => {
    expect(clamp(-5, RUN)).toBe(0);
    expect(clamp(99 * DAY_S, RUN)).toBe(41 * DAY_S);
  });
});

describe("the days", () => {
  it("moves a day on or back at the same time of day, held to what is computed", () => {
    const six = 17 * DAY_S + 6 * 3600;
    expect(dayAway(six, 1, RUN)).toBe(18 * DAY_S + 6 * 3600);
    expect(dayAway(six, -1, RUN)).toBe(16 * DAY_S + 6 * 3600);
    expect(dayAway(100, -1, RUN)).toBe(0);
    expect(dayAway(41 * DAY_S - 100, 1, RUN)).toBe(41 * DAY_S);
  });

  it("are counted from 1 in a label", () => {
    expect(dayLabel(0)).toBe("Day 1, 00:00");
    expect(dayLabel(17 * DAY_S + 6 * 3600)).toBe("Day 18, 06:00");
  });

  it("give a day's last moment as its midnight", () => {
    expect(dayLabel(DAY_S)).toBe("Day 1, 24:00");
    expect(dayLabel(DAY_S + 60)).toBe("Day 2, 00:01");
  });

  it("are computed once their last moment is", () => {
    expect(computedText(RUN)).toBe("41 of 120 days computed");
    expect(computedText({ ...RUN, frontierS: 41 * DAY_S - 1 })).toBe("40 of 120 days computed");
    expect(computedText({ startS: 0, frontierS: 3 * DAY_S, endS: null })).toBe("3 days computed");
    // Before its first day is whole, none is: said as a count, not as "day 0".
    expect(computedText({ ...RUN, frontierS: DAY_S - 1 })).toBe("0 of 120 days computed");
    expect(computedText({ startS: 0, frontierS: DAY_S, endS: null })).toBe("1 day computed");
  });

  it("are ticked at a step that reads well", () => {
    expect(dayTicks(RUN)).toEqual([0, 30, 60, 90, 120]);
    expect(dayTicks({ startS: 0, frontierS: 3 * DAY_S, endS: 5 * DAY_S })).toEqual([
      0, 1, 2, 3, 4, 5,
    ]);
  });

  it("say a fork's other layout, in words, or nothing of one that stays in its own", () => {
    const fork = { epoch: 0, at_s: DAY_S * 1.5 };

    expect(forkedText({ ...fork, layout: null })).toBe("forked from epoch 0 at Day 2, 12:00");
    expect(forkedText({ ...fork, layout: "open" })).toBe(
      "forked from epoch 0 at Day 2, 12:00 into layout open",
    );
    expect(forkedText({ ...fork, layout: "default~heater:-1:0.5" })).toBe(
      "forked from epoch 0 at Day 2, 12:00 into layout default with items moved",
    );
  });

  it("label where a fork's timeline begins, in place of a tick too near it", () => {
    const from = (first: number, end: number) =>
      dayTicks({ startS: first * DAY_S, frontierS: first * DAY_S, endS: end * DAY_S });

    expect(from(4, 24)).toEqual([4, 10, 15, 20, 24]);
    expect(from(1, 120)).toEqual([1, 30, 60, 90, 120]);
    expect(from(29, 120)).toEqual([29, 60, 90, 120]);
    // A start that is itself a tick is not labelled twice.
    expect(from(30, 120)).toEqual([30, 60, 90, 120]);
  });

  it("always label the timeline's end, in place of a tick too near it", () => {
    const of = (days: number) => dayTicks({ startS: 0, frontierS: DAY_S, endS: days * DAY_S });

    expect(of(21)).toEqual([0, 5, 10, 15, 21]);
  });

  it("tick a short run evenly, not at a week's step cut short by its end", () => {
    const of = (days: number) => dayTicks({ startS: 0, frontierS: DAY_S, endS: days * DAY_S });

    expect(of(10)).toEqual([0, 2, 4, 6, 8, 10]);
    expect(of(8)).toEqual([0, 2, 4, 6, 8]);
    expect(of(30)).toEqual([0, 5, 10, 15, 20, 25, 30]);
  });
});

describe("the keys", () => {
  const at = 10 * DAY_S;

  it("move the handle an hour, or a day, and hold it to what is computed", () => {
    expect(movedByKey("ArrowRight", at, RUN)).toBe(at + 3600);
    expect(movedByKey("ArrowLeft", at, RUN)).toBe(at - 3600);
    expect(movedByKey("PageUp", at, RUN)).toBe(at + DAY_S);
    expect(movedByKey("ArrowRight", 41 * DAY_S, RUN)).toBe(41 * DAY_S);
  });

  it("take the handle to the ends of what is computed", () => {
    expect(movedByKey("Home", at, RUN)).toBe(0);
    expect(movedByKey("End", at, RUN)).toBe(41 * DAY_S);
  });

  it("leave any other key alone", () => {
    expect(movedByKey("a", at, RUN)).toBeNull();
  });
});
