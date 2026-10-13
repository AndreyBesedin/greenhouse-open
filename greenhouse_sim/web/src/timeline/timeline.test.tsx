import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import { TimelineLanes, TimelinePanel } from "./TimelinePanel";
import {
  describeTurn,
  eventsAt,
  loadTimeline,
  parseTimeline,
  timelineUrl,
  timelineWindow,
} from "./timeline";

// The first ten minutes of a run: a heater switched on at 10 min, and the
// air, two sensors and a camera every five minutes.
const BODY = {
  from_s: 0,
  until_s: 600,
  processes: ["commands", "air", "plants", "sensors", "cameras"],
  subjects: ["t_front", "t_back", "cam", "house", "heater"],
  kinds: ["sample", "frame", "step", "set to 1"],
  times_s: [0, 0, 0, 300, 300, 300, 300, 600, 600, 600, 600, 600],
  process: [3, 3, 4, 1, 3, 3, 4, 0, 1, 3, 3, 4],
  subject: [0, 1, 2, 3, 0, 1, 2, 4, 3, 0, 1, 2],
  kind: [0, 0, 1, 2, 0, 0, 1, 3, 2, 0, 0, 1],
};

describe("a run's timeline", () => {
  it("lies in a window of its zoom, a moment at a window's end in the one it ends", () => {
    expect(timelineWindow(600, 3600)).toEqual({ fromS: 0, untilS: 3600 });
    expect(timelineWindow(0, 3600)).toEqual({ fromS: 0, untilS: 3600 });
    expect(timelineWindow(3600, 3600)).toEqual({ fromS: 0, untilS: 3600 });
    expect(timelineWindow(DAY_S + 600, DAY_S)).toEqual({ fromS: DAY_S, untilS: 2 * DAY_S });
    expect(timelineWindow(DAY_S + 61, 60)).toEqual({ fromS: DAY_S + 60, untilS: DAY_S + 120 });
  });

  it("is asked for as the climate is, over its window", () => {
    expect(
      timelineUrl(
        "climate_box",
        {
          levels: { heater: 1 },
          schedule: [{ timeS: 300, actuatorId: "fan", level: 1 }],
          daily: [{ timeS: 64800, actuatorId: "heater", level: 0 }],
          openings: { roof_vent: 1 },
          time: 600,
          weather: "cold_spring_day",
        },
        { fromS: 0, untilS: 3600 },
      ),
    ).toBe(
      "/api/scenarios/climate_box/timeline?set=heater:1&schedule=300:fan:1&daily=64800:heater:0&from=0&t=3600",
    );
  });

  it("is checked rather than trusted", async () => {
    const answered = (async () => Response.json(BODY)) as typeof fetch;
    const refused = (async () => new Response("{}", { status: 400 })) as typeof fetch;

    expect(await loadTimeline("/x", answered)).toMatchObject({ status: "loaded" });
    expect(await loadTimeline("/x", refused)).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 400",
    });
    expect(() => parseTimeline({ ...BODY, kind: [0] })).toThrow("not what the viewer");
  });

  it("says what each process does at a moment, in the order they take their turns", () => {
    const timeline = parseTimeline(BODY);
    const at = eventsAt(timeline, 600);

    expect(at.map((event) => event.process)).toEqual([
      "commands",
      "air",
      "sensors",
      "sensors",
      "cameras",
    ]);
    expect(describeTurn(at.slice(0, 1))).toBe("heater set to 1");
    const many = Array.from({ length: 13 }, (_, n) => ({ ...at[2], subject: `t_${n}` }));
    expect(describeTurn(many as typeof at)).toBe("13 × sample");
  });

  it("draws a lane per process, its events as ticks, and the moment's turns", () => {
    const html = renderToStaticMarkup(<TimelineLanes timeline={parseTimeline(BODY)} time={600} />);

    expect(html).toContain('data-testid="timeline-sensors">sensors, 6<');
    expect(html).toContain('data-testid="timeline-plants">plants, 0<');
    // The sensors' six samples at three moments: three ticks.
    expect(html).toContain('class="timeline-ticks" d="M0 0V10M120 0V10M240 0V10"');
    expect(html).toContain('class="timeline-now" x1="240" x2="240"');
    expect(html.match(/data-testid="timeline-turn"/g)).toHaveLength(4);
    expect(html).toContain("commands: heater set to 1");
  });

  it("is asked for only once opened", () => {
    const html = renderToStaticMarkup(
      <TimelinePanel scenarioId="climate_box" run={{}} time={600} />,
    );

    expect(html).toContain("<summary>Timeline</summary>");
    expect(html).not.toContain("Listing the run");
  });
});
