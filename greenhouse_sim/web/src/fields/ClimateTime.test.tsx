// @vitest-environment jsdom
import { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { dayLabel } from "../replay/timeline";
import { searchFor, sourceFromSearch } from "../scene/source";
import { render, said } from "../testing/render";
import { ClimateTime, describeClimateRun, describeTime, onDay, REPLAYED_NOTE } from "./ClimateTime";
import { fieldUrl } from "./source";

const ignore = () => undefined;

describe("a climate run's moment", () => {
  it("is written in minutes, and in hours and minutes after the first hour", () => {
    expect(describeTime(0)).toBe("0 min");
    expect(describeTime(600)).toBe("10 min");
    expect(describeTime(90)).toBe("1.5 min");
    expect(describeTime(3600)).toBe("1 h 00 min");
    expect(describeTime(5 * 3600 + 300)).toBe("5 h 05 min");
    expect(describeTime(86_400)).toBe("24 h 00 min");
  });

  it("is written with its day after the first, a day ending at its midnight", () => {
    expect(describeTime(DAY_S + 600)).toBe("day 2, 10 min");
    expect(describeTime(3 * DAY_S + 5 * 3600 + 300)).toBe("day 4, 5 h 05 min");
    expect(describeTime(2 * DAY_S)).toBe("day 2, 24 h 00 min");
  });

  it("is on the day a replay's timeline says, beside it on one page", () => {
    // A replay's "Day 4, 12:00" beside a panel's moment (the QA of 2026-11-04).
    const noon = 3 * DAY_S + 12 * 3600;

    expect(dayLabel(noon)).toBe("Day 4, 12:00");
    expect(describeTime(noon)).toBe("day 4, 12 h 00 min");
  });

  it("keeps its time of day on another day, a later day's from a minute after midnight", () => {
    expect(onDay(3, 600)).toBe(3 * DAY_S + 600);
    expect(onDay(0, 0)).toBe(0);
    expect(onDay(3, 0)).toBe(3 * DAY_S + 60);
    expect(onDay(2, DAY_S)).toBe(3 * DAY_S);
  });

  it("is chosen on a slider over the day, a minute at a time, with no play of its own", () => {
    const html = renderToStaticMarkup(
      <ClimateTime time={600} shown={540} days={1} onTime={ignore} />,
    );

    expect(html).toContain('aria-label="Climate run"');
    expect(html).toContain(
      `type="range" aria-label="Time of day" min="0" max="${DAY_S}" step="60" value="600"`,
    );
    // Until the moment asked for arrives, the one drawn is shown.
    expect(html).toContain('data-testid="climate-time">9 min<');
    // A run computed and kept is watched in a replay (decision 0074).
    expect(html).not.toContain("<button");
    // A run of a day has no days to choose.
    expect(html).not.toContain("Day of the run");
  });

  it("is chosen on a day of a longer run, a day at a time", () => {
    const html = renderToStaticMarkup(
      <ClimateTime time={3 * DAY_S + 600} shown={3 * DAY_S + 600} days={14} onTime={ignore} />,
    );

    expect(html).toContain(
      `type="range" aria-label="Time of day" min="60" max="${DAY_S}" step="60" value="600"`,
    );
    // The slider's value counts from 0; it is heard as the day it names.
    expect(html).toContain(
      'type="range" aria-label="Day of the run" min="0" max="13" step="1" aria-valuetext="day 4" value="3"',
    );
    expect(html).toContain('data-testid="climate-time">day 4, 10 min<');
    expect(html).toContain('aria-label="Previous day">');
    expect(html).toContain('aria-label="Next day">');
    expect(html).not.toContain("<select");
  });

  it("can go no day past its first or its last", () => {
    const first = renderToStaticMarkup(
      <ClimateTime time={600} shown={600} days={2} onTime={ignore} />,
    );
    const last = renderToStaticMarkup(
      <ClimateTime time={DAY_S + 600} shown={DAY_S + 600} days={2} onTime={ignore} />,
    );

    expect(first).toContain('aria-label="Previous day" disabled="">');
    expect(first).not.toContain('aria-label="Next day" disabled=""');
    expect(last).toContain('aria-label="Next day" disabled="">');
  });

  it("is kept in the address with the field, and asked of the climate alone", () => {
    const source = sourceFromSearch("?scenario=climate_box&field=climate&t=600&set=heater:1");

    expect(source).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      field: "climate",
      time: 600,
      levels: { heater: 1 },
    });
    expect(searchFor(source)).toBe("?scenario=climate_box&set=heater:1&field=climate&t=600");
    expect(sourceFromSearch("?scenario=climate_box&t=600")).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
    });
    expect(sourceFromSearch("?scenario=climate_box&field=climate&t=-5")).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      field: "climate",
    });
    expect(fieldUrl("climate_box", "climate", { time: 600 })).toBe(
      "/api/scenarios/climate_box/fields/climate?t=600",
    );
    expect(fieldUrl("climate_box", "climate", { time: 0 })).toBe(
      "/api/scenarios/climate_box/fields/climate",
    );
    expect(fieldUrl("climate_box", "shear", { time: 600 })).toBe(
      "/api/scenarios/climate_box/fields/shear",
    );
    // Under another weather, which only its climate depends on.
    expect(fieldUrl("climate_box", "climate", { time: 600, weather: "cold_spring_day" })).toBe(
      "/api/scenarios/climate_box/fields/climate?t=600&weather=cold_spring_day",
    );
    expect(fieldUrl("climate_box", "uniform", { weather: "cold_spring_day" })).toBe(
      "/api/scenarios/climate_box/fields/uniform",
    );
  });
});

describe("a climate run's moment on its way", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  function clock(props: {
    time: number;
    shown: number | null;
    failed?: boolean;
    followed?: boolean;
  }) {
    return <ClimateTime {...props} days={14} onTime={ignore} />;
  }

  it("says which moment it is loading, and for how long, beside the one drawn", () => {
    const view = render(clock({ time: DAY_S + 600, shown: 600 }));

    expect(said(view.container, "climate-time")).toBe("10 min");
    expect(said(view.container, "climate-pending")).toBe("Loading day 2, 10 min… 0 s");
    act(() => {
      vi.advanceTimersByTime(3_000);
    });

    expect(said(view.container, "climate-pending")).toBe("Loading day 2, 10 min… 3 s");
    view.unmount();
  });

  it("counts afresh for the next moment asked for", () => {
    const view = render(clock({ time: DAY_S + 600, shown: 600 }));
    act(() => {
      vi.advanceTimersByTime(5_000);
    });

    view.rerender(clock({ time: 2 * DAY_S + 600, shown: DAY_S + 600 }));

    expect(said(view.container, "climate-pending")).toBe("Loading day 3, 10 min… 0 s");
    view.unmount();
  });

  it("keeps the loading line's place between loads while a replay is followed (#301)", () => {
    const notes = (container: HTMLElement) => container.querySelectorAll(".climate-time-note");
    const view = render(clock({ time: DAY_S + 600, shown: 600, followed: true }));
    const loading = notes(view.container).length;

    view.rerender(clock({ time: DAY_S + 600, shown: DAY_S + 600, followed: true }));

    // The same lines, the loading one kept, unseen and unread.
    expect(notes(view.container)).toHaveLength(loading);
    const idle = view.container.querySelector(".climate-time-idle");
    expect(idle?.getAttribute("aria-hidden")).toBe("true");
    expect(said(view.container, "climate-pending")).toBeNull();
    view.unmount();
  });

  it("keeps no line for loading once a moment has arrived, at rest", () => {
    const view = render(clock({ time: DAY_S + 600, shown: DAY_S + 600 }));

    expect(view.container.querySelector(".climate-time-idle")).toBeNull();
    view.unmount();
  });

  it("says nothing more once it has arrived", () => {
    const view = render(clock({ time: DAY_S + 600, shown: DAY_S + 600 }));

    expect(said(view.container, "climate-pending")).toBeNull();
    expect(said(view.container, "climate-failed")).toBeNull();
    view.unmount();
  });

  it("says, when it cannot be drawn, which moment is drawn instead", () => {
    const view = render(clock({ time: DAY_S + 600, shown: 600, failed: true }));

    expect(said(view.container, "climate-pending")).toBeNull();
    expect(said(view.container, "climate-failed")).toBe(
      "Day 2, 10 min cannot be drawn; 10 min is shown.",
    );
    view.unmount();
  });
});

describe("a climate run's moment, its section folded (#273)", () => {
  it("says the moment drawn once it has arrived", () => {
    expect(describeClimateRun(DAY_S + 600, DAY_S + 600, false)).toBe("Climate run: day 2, 10 min");
  });

  it("says the moment drawn and the one on its way, never the one on its way alone", () => {
    expect(describeClimateRun(DAY_S + 600, 600, false)).toBe(
      "Climate run: 10 min; loading day 2, 10 min…",
    );
    expect(describeClimateRun(600, null, false)).toBe("Climate run: loading 10 min…");
  });

  it("says the moment asked for cannot be drawn, beside the one drawn", () => {
    expect(describeClimateRun(DAY_S + 600, 600, true)).toBe(
      "Climate run: 10 min; day 2, 10 min cannot be drawn",
    );
    expect(describeClimateRun(600, null, true)).toBe("Climate run: 10 min cannot be drawn");
  });
});

describe("a climate run's moment, in a view that follows the run played back", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  function followed(props: { time: number; shown: number | null; failed?: boolean }) {
    return <ClimateTime {...props} followed days={14} onTime={ignore} />;
  }

  it("leaves its controls to a replay's timeline, and says that one in the run's place (P17.6)", () => {
    const view = render(
      <ClimateTime time={DAY_S} shown={DAY_S} followed days={14} onTime={ignore} />,
    );

    expect(view.container.querySelectorAll("button, input, select")).toHaveLength(0);
    expect(said(view.container, "climate-followed")).toBe(REPLAYED_NOTE);
    expect(REPLAYED_NOTE).not.toContain("Stop following");
  });

  it("leaves the sliders and the day steps to what follows it, and gets them back", () => {
    // A slider over one day would say a state the run is not in (#270).
    const view = render(followed({ time: 3 * DAY_S + 600, shown: 3 * DAY_S + 600 }));

    expect(view.container.querySelectorAll("button, input, select")).toHaveLength(0);
    expect(said(view.container, "climate-time")).toBe("day 4, 10 min");
    expect(said(view.container, "climate-followed")).toBe(REPLAYED_NOTE);
    // No longer followed, its sliders and day steps are back.
    view.rerender(
      <ClimateTime time={3 * DAY_S + 600} shown={3 * DAY_S + 600} days={14} onTime={ignore} />,
    );

    expect(view.container.querySelectorAll('input[type="range"]')).toHaveLength(2);
    expect(view.container.querySelectorAll("button")).toHaveLength(2);
    expect(said(view.container, "climate-followed")).toBeNull();
    view.unmount();
  });

  it("still says which moment is on its way, and which cannot be drawn", () => {
    const view = render(followed({ time: DAY_S + 600, shown: 600 }));

    expect(said(view.container, "climate-time")).toBe("10 min");
    expect(said(view.container, "climate-pending")).toBe("Loading day 2, 10 min… 0 s");
    expect(said(view.container, "climate-followed")).not.toBeNull();
    view.rerender(followed({ time: DAY_S + 600, shown: 600, failed: true }));

    expect(said(view.container, "climate-failed")).toBe(
      "Day 2, 10 min cannot be drawn; 10 min is shown.",
    );
    view.unmount();
  });

  it("never moves the moment on by itself, followed or not", () => {
    for (const followed of [true, false]) {
      const onTime = vi.fn();
      const view = render(
        <ClimateTime
          time={DAY_S + 600}
          shown={DAY_S + 600}
          followed={followed}
          days={14}
          onTime={onTime}
        />,
      );
      act(() => {
        vi.advanceTimersByTime(5_000);
      });

      expect(onTime).not.toHaveBeenCalled();
      view.unmount();
    }
  });
});
