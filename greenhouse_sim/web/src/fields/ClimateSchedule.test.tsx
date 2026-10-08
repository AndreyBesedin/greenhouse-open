import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  levelsAt,
  type ScheduledCommand,
  scheduleFrom,
  scheduleText,
  searchFor,
  sourceFromSearch,
  withOverride,
} from "../scene/source";
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
    expect(describeCommand({ timeS: 0, actuatorId: "heater", level: 0 })).toBe("heater off");
    expect(
      renderToStaticMarkup(
        <ClimateSchedule schedule={[]} time={0} onTime={ignore} onRemove={ignore} />,
      ),
    ).toBe("");
  });
});
