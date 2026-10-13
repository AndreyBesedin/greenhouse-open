import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import { runsSomething, scenarioRun } from "../scene/run";
import {
  latestDaily,
  levelsAt,
  type ScheduledCommand,
  scheduleFrom,
  scheduleText,
  searchFor,
  sourceFromSearch,
  withOverride,
} from "../scene/source";
import { sensorsUrl } from "../sensors/readings";
import { ClimateSchedule, describeCommand } from "./ClimateSchedule";
import { fieldUrl } from "./source";

const ignore = () => undefined;
const SCHEDULE: ScheduledCommand[] = [
  { timeS: 60, actuatorId: "fan", level: 1 },
  { timeS: 300, actuatorId: "heater", level: 1 },
  { timeS: 300, actuatorId: "heater", level: 0.5 },
];

describe("a climate run's schedule", () => {
  it("is kept in the address with its climate, in the order given", () => {
    const source = sourceFromSearch(
      "?scenario=climate_box&field=climate&t=600&schedule=60:fan:1,300:heater:1,300:heater:0.5",
    );

    expect(source).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      field: "climate",
      time: 600,
      schedule: SCHEDULE,
    });
    expect(searchFor(source)).toBe(
      "?scenario=climate_box&field=climate&t=600&schedule=60:fan:1,300:heater:1,300:heater:0.5",
    );
    expect(scheduleFrom("60:fan")).toBeNull();
    expect(scheduleFrom("soon:fan:1")).toBeNull();
    expect(fieldUrl("climate_box", "climate", { schedule: SCHEDULE })).toBe(
      `/api/scenarios/climate_box/fields/climate?schedule=${scheduleText(SCHEDULE)}`,
    );
    expect(fieldUrl("climate_box", "uniform", { schedule: SCHEDULE })).toBe(
      "/api/scenarios/climate_box/fields/uniform",
    );
  });

  it("sets the equipment's levels at each moment, after those set from the start", () => {
    const run = { levels: { fan: 0.5, heater: 0 }, schedule: SCHEDULE };

    expect(levelsAt({ ...run, time: 0 })).toEqual({ fan: 0.5, heater: 0 });
    expect(levelsAt({ ...run, time: 60 })).toEqual({ fan: 1, heater: 0 });
    // The later command at a moment wins.
    expect(levelsAt({ ...run, time: 600 })).toEqual({ fan: 1, heater: 0.5 });
  });

  it("takes an override at its moment, in place of a command to the same equipment then", () => {
    const overridden = withOverride(SCHEDULE, 300, { heater: 0 });
    const later = withOverride(SCHEDULE, 120, { dehumidifier: 1 });

    expect(overridden).toEqual([SCHEDULE[0], { timeS: 300, actuatorId: "heater", level: 0 }]);
    expect(later.map((command) => command.timeS)).toEqual([60, 120, 300, 300]);
  });

  it("is listed under the time slider, each command to go to or take out", () => {
    const html = renderToStaticMarkup(
      <ClimateSchedule schedule={SCHEDULE} time={120} onTime={ignore} onRemove={ignore} />,
    );

    expect(html).toContain('aria-label="Schedule"');
    expect(html.match(/data-testid="schedule-command"/g)).toHaveLength(3);
    expect(html).toContain('data-applied="true"');
    expect(html).toContain('aria-label="Go to heater 50% at 5 min"');
    expect(html).toContain('aria-label="Remove heater 50% at 5 min"');
    expect(html.match(/data-testid="schedule-marker"/g)).toHaveLength(3);
    expect(describeCommand({ timeS: 0, actuatorId: "heater", level: 0 })).toBe("heater off");
    expect(
      renderToStaticMarkup(
        <ClimateSchedule schedule={[]} time={0} onTime={ignore} onRemove={ignore} />,
      ),
    ).toBe("");
  });

  it("is kept in the address with its daily commands, and asked of the climate with them", () => {
    const source = sourceFromSearch(
      "?scenario=climate_box&field=climate&t=600&schedule=60:fan:1&daily=64800:heater:1",
    );

    expect(source).toMatchObject({ daily: [{ timeS: 64800, actuatorId: "heater", level: 1 }] });
    expect(searchFor(source)).toBe(
      "?scenario=climate_box&field=climate&t=600&schedule=60:fan:1&daily=64800:heater:1",
    );
    expect(sourceFromSearch("?scenario=climate_box&daily=64800:heater:1")).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
    });
    if (source.kind === "scenario") {
      expect(fieldUrl("climate_box", "climate", scenarioRun(source))).toBe(
        "/api/scenarios/climate_box/fields/climate?schedule=60:fan:1&daily=64800:heater:1&t=600",
      );
      expect(sensorsUrl("climate_box", "truth", scenarioRun(source))).toBe(
        "/api/scenarios/climate_box/climate/truth?schedule=60:fan:1&daily=64800:heater:1&t=600",
      );
      expect(runsSomething({ daily: source.daily })).toBe(true);
    }
  });

  it("sets the levels its daily commands set, each at its latest moment", () => {
    const evenings = {
      daily: [
        { timeS: 64800, actuatorId: "heater", level: 1 },
        { timeS: 79200, actuatorId: "heater", level: 0 },
      ],
    };

    expect(levelsAt({ ...evenings, time: 600 })).toEqual({});
    expect(levelsAt({ ...evenings, time: 72000 })).toEqual({ heater: 1 });
    expect(levelsAt({ ...evenings, time: DAY_S + 600 })).toEqual({ heater: 0 });
    expect(levelsAt({ ...evenings, time: DAY_S + 72000 })).toEqual({ heater: 1 });
    // A command for a moment overrides the day's then.
    const overridden = {
      ...evenings,
      schedule: [{ timeS: 64800, actuatorId: "heater", level: 0 }],
    };
    expect(levelsAt({ ...overridden, time: 72000 })).toEqual({ heater: 0 });
    expect(levelsAt({ ...overridden, time: DAY_S + 72000 })).toEqual({ heater: 1 });
    expect(latestDaily({ timeS: 64800, actuatorId: "heater", level: 1 }, 2 * DAY_S)).toBe(
      DAY_S + 64800,
    );
  });

  it("lists its daily commands, each marked on every day, to go to or take out", () => {
    const html = renderToStaticMarkup(
      <ClimateSchedule
        schedule={[{ timeS: DAY_S + 600, actuatorId: "fan", level: 1 }]}
        daily={[{ timeS: 64800, actuatorId: "heater", level: 1 }]}
        time={DAY_S + 43_200}
        onTime={ignore}
        onRemove={ignore}
        onRepeat={ignore}
        onRemoveDaily={ignore}
      />,
    );

    expect(html.match(/data-testid="daily-command"/g)).toHaveLength(1);
    expect(html).toContain('aria-label="Go to heater 100% every day at 18 h 00 min"');
    expect(html).toContain('aria-label="Remove heater 100% every day at 18 h 00 min"');
    expect(html).toContain('aria-label="Repeat fan 100% at day 1, 10 min every day"');
    // Today's evening is still to come; the fan's command has come.
    expect(html).toContain('class="to-come daily" style="left:75%"');
    expect(html.match(/data-testid="schedule-marker"/g)).toHaveLength(2);
  });

  it("marks on its bar only the moment's day's commands, across that day", () => {
    const days: ScheduledCommand[] = [
      { timeS: 600, actuatorId: "heater", level: 1 },
      { timeS: DAY_S + 21_600, actuatorId: "heater", level: 0 },
      { timeS: 2 * DAY_S + 600, actuatorId: "fan", level: 1 },
    ];
    const html = renderToStaticMarkup(
      <ClimateSchedule schedule={days} time={DAY_S + 43_200} onTime={ignore} onRemove={ignore} />,
    );

    expect(html.match(/data-testid="schedule-marker"/g)).toHaveLength(1);
    expect(html).toContain('class="applied" style="left:25%"');
    // Every command is listed, each at its day.
    expect(html.match(/data-testid="schedule-command"/g)).toHaveLength(3);
    expect(html).toContain('aria-label="Go to heater off at day 1, 6 h 00 min"');
    expect(html).toContain('aria-label="Go to fan 100% at day 2, 10 min"');
  });
});
