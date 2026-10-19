// @vitest-environment jsdom
import { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { searchFor, sourceFromSearch } from "../scene/source";
import { render, said } from "../testing/render";
import { ClimateTime, describeTime, onDay, playStep } from "./ClimateTime";
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
    expect(describeTime(DAY_S + 600)).toBe("day 1, 10 min");
    expect(describeTime(3 * DAY_S + 5 * 3600 + 300)).toBe("day 3, 5 h 05 min");
    expect(describeTime(2 * DAY_S)).toBe("day 1, 24 h 00 min");
  });

  it("plays a minute at a time through the first hour, and five after it", () => {
    expect(playStep(600)).toBe(60);
    expect(playStep(3600)).toBe(300);
  });

  it("plays at the pace chosen", () => {
    expect(playStep(600, 3600)).toBe(3600);
    expect(playStep(600, DAY_S)).toBe(DAY_S);
    expect(playStep(DAY_S + 600)).toBe(300);
  });

  it("keeps its time of day on another day, a later day's from a minute after midnight", () => {
    expect(onDay(3, 600)).toBe(3 * DAY_S + 600);
    expect(onDay(0, 0)).toBe(0);
    expect(onDay(3, 0)).toBe(3 * DAY_S + 60);
    expect(onDay(2, DAY_S)).toBe(3 * DAY_S);
  });

  it("is chosen on a slider over the day, a minute at a time, and played", () => {
    const html = renderToStaticMarkup(
      <ClimateTime
        time={600}
        shown={540}
        days={1}
        playing={false}
        onTime={ignore}
        onPlaying={ignore}
      />,
    );

    expect(html).toContain('aria-label="Climate run"');
    expect(html).toContain(
      `type="range" aria-label="Time of day" min="0" max="${DAY_S}" step="60" value="600"`,
    );
    // Until the moment asked for arrives, the one drawn is shown.
    expect(html).toContain('data-testid="climate-time">9 min<');
    expect(html).toContain(">Play</button>");
    // A run of a day has no days to choose.
    expect(html).not.toContain("Day of the run");
  });

  it("is chosen on a day of a longer run, a day at a time, at a pace", () => {
    const html = renderToStaticMarkup(
      <ClimateTime
        time={3 * DAY_S + 600}
        shown={3 * DAY_S + 600}
        days={14}
        playing={false}
        onTime={ignore}
        onPlaying={ignore}
      />,
    );

    expect(html).toContain(
      `type="range" aria-label="Time of day" min="60" max="${DAY_S}" step="60" value="600"`,
    );
    expect(html).toContain(
      'type="range" aria-label="Day of the run" min="0" max="13" step="1" value="3"',
    );
    expect(html).toContain('data-testid="climate-time">day 3, 10 min<');
    expect(html).toContain('aria-label="Previous day">');
    expect(html).toContain('aria-label="Next day">');
    expect(html).toContain('<select aria-label="Pace">');
    expect(html).toContain(">1 day a step</option>");
  });

  it("can go no day past its first or its last", () => {
    const first = renderToStaticMarkup(
      <ClimateTime
        time={600}
        shown={600}
        days={2}
        playing={false}
        onTime={ignore}
        onPlaying={ignore}
      />,
    );
    const last = renderToStaticMarkup(
      <ClimateTime
        time={DAY_S + 600}
        shown={DAY_S + 600}
        days={2}
        playing={false}
        onTime={ignore}
        onPlaying={ignore}
      />,
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
    playing?: boolean;
  }) {
    const { playing = false, ...rest } = props;
    return <ClimateTime {...rest} days={14} playing={playing} onTime={ignore} onPlaying={ignore} />;
  }

  it("says which moment it is loading, and for how long, beside the one drawn", () => {
    const view = render(clock({ time: DAY_S + 600, shown: 600 }));

    expect(said(view.container, "climate-time")).toBe("10 min");
    expect(said(view.container, "climate-pending")).toBe("Loading day 1, 10 min… 0 s");
    act(() => {
      vi.advanceTimersByTime(3_000);
    });

    expect(said(view.container, "climate-pending")).toBe("Loading day 1, 10 min… 3 s");
    view.unmount();
  });

  it("says play is waiting for it, and counts afresh for the next", () => {
    const view = render(clock({ time: DAY_S + 600, shown: 600, playing: true }));
    act(() => {
      vi.advanceTimersByTime(5_000);
    });

    view.rerender(clock({ time: 2 * DAY_S + 600, shown: DAY_S + 600, playing: true }));

    expect(said(view.container, "climate-pending")).toBe("Playing: waiting for day 2, 10 min… 0 s");
    view.unmount();
  });

  it("says nothing more once it has arrived", () => {
    const view = render(clock({ time: DAY_S + 600, shown: DAY_S + 600 }));

    expect(said(view.container, "climate-pending")).toBeNull();
    expect(said(view.container, "climate-failed")).toBeNull();
    view.unmount();
  });

  it("stops play when it cannot be drawn, and says which moment is drawn instead", () => {
    // Play waits for the moment asked for, which a failure never brings:
    // waiting on, it would look stuck (#202).
    const onPlaying = vi.fn();
    const view = render(
      <ClimateTime
        time={DAY_S + 600}
        shown={600}
        failed
        days={14}
        playing
        onTime={ignore}
        onPlaying={onPlaying}
      />,
    );

    expect(onPlaying).toHaveBeenCalledExactlyOnceWith(false);
    expect(said(view.container, "climate-pending")).toBeNull();
    expect(said(view.container, "climate-failed")).toBe(
      "Day 1, 10 min cannot be drawn; 10 min is shown.",
    );
    view.unmount();
  });
});
