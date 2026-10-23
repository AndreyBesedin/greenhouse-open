import { describe, expect, it } from "vitest";

import { ownDaily } from "../scenarios";
import { keptDaily, type ScenarioSource, standingAt, withOwnDaily, withoutDaily } from "./edits";
import { runParameters } from "./run";
import { type ScheduledCommand, searchFor, sourceFromSearch } from "./source";

// The reference run's heater on every evening and set back at night, as a
// scenario's own daily commands (P09.4).
const OWN: ScheduledCommand[] = [
  { timeS: 61200, actuatorId: "heater", level: 1 },
  { timeS: 82800, actuatorId: "heater", level: 0.8 },
];

function scenario(search: string): ScenarioSource {
  const source = sourceFromSearch(search);
  if (source.kind !== "scenario") {
    throw new Error("not a scenario");
  }
  return source;
}

describe("a scenario's own daily commands", () => {
  it("are listed with the scenario, as the viewer writes commands", () => {
    const summary = {
      id: "reference_greenhouse",
      name: "Reference greenhouse",
      description: "",
      plants: 32,
      duration_days: 120,
      layouts: ["default"],
      daily: [
        { time_of_day_s: 61200, actuator_id: "heater", level: 1 },
        { time_of_day_s: 82800, actuator_id: "heater", level: 0.8 },
      ],
    };

    expect(ownDaily(summary)).toEqual(OWN);
    expect(ownDaily(undefined)).toEqual([]);
  });

  it("are drawn where the address gives none, and none where it says none", () => {
    const own = withOwnDaily(scenario("?scenario=reference_greenhouse&field=climate"), OWN);
    const none = scenario("?scenario=reference_greenhouse&field=climate&daily=none");

    expect(own.daily).toEqual(OWN);
    expect(none.daily).toEqual([]);
    expect(withOwnDaily(none, OWN)).toBe(none);
    // A scenario without its own changes nothing.
    const plain = scenario("?scenario=climate_box&field=climate");
    expect(withOwnDaily(plain, [])).toBe(plain);
  });

  it("are asked for as the run's, and none as none", () => {
    const own = withOwnDaily(scenario("?scenario=reference_greenhouse&field=climate"), OWN);

    expect(runParameters(own)).toEqual(["daily=61200:heater:1,82800:heater:0.8"]);
    expect(runParameters({ daily: [] })).toEqual(["daily=none"]);
    expect(runParameters({})).toEqual([]);
  });

  it("are kept in the address only where they differ from the scenario's own", () => {
    const own = withOwnDaily(scenario("?scenario=reference_greenhouse&field=climate"), OWN);
    const fewer = withoutDaily(own, 0);
    const none = withoutDaily(fewer, 0);

    expect(keptDaily(own, OWN).daily).toBeUndefined();
    expect(searchFor(keptDaily(own, OWN))).toBe("?scenario=reference_greenhouse&field=climate");
    expect(keptDaily(fewer, OWN).daily).toEqual([OWN[1]]);
    expect(none.daily).toEqual([]);
    expect(searchFor(keptDaily(none, OWN))).toBe(
      "?scenario=reference_greenhouse&field=climate&daily=none",
    );
  });
});

describe("a scenario's scene at a moment", () => {
  it("draws its equipment at their levels, and its doors and vents as far open as commanded", () => {
    const source = scenario(
      "?scenario=reference_greenhouse&field=climate&t=40000&daily=32400:roof_vent_1:0.5,32400:heater:1",
    );

    expect(standingAt(source, ["roof_vent_1", "door"])).toMatchObject({
      levels: { heater: 1 },
      openings: { roof_vent_1: 0.5 },
    });
    // Without its doors and vents named, every command is equipment's.
    expect(standingAt(source, []).levels).toEqual({ heater: 1, roof_vent_1: 0.5 });
  });

  it("draws a heater its thermostat runs as the run has it", () => {
    const source = scenario("?scenario=reference_greenhouse&field=climate&t=3600");

    expect(standingAt(source, [], { heater: 1 }).levels).toEqual({ heater: 1 });
    expect(standingAt(source, []).levels).toEqual({});
  });
});
