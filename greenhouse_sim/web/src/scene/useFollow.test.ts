import { describe, expect, it } from "vitest";

import type { SceneSource } from "./source";
import { runChanges, withoutRunChanges } from "./useFollow";

type ScenarioSource = Extract<SceneSource, { kind: "scenario" }>;

const FOLLOWED: ScenarioSource = {
  kind: "scenario",
  scenarioId: "reference_greenhouse",
  follow: true,
  time: 3600,
};

describe("the run a followed view draws, against the one played back", () => {
  it("is the same run while the address changes nothing of it", () => {
    expect(runChanges(FOLLOWED, "default")).toEqual([]);
    // The moment, the field and the camera are the view's, not the run's.
    expect(runChanges({ ...FOLLOWED, field: "climate" }, "default")).toEqual([]);
  });

  it("names each change that makes it another run", () => {
    const changed: ScenarioSource = {
      ...FOLLOWED,
      layout: "propagation",
      weather: "cold",
      levels: { heater: 0 },
    };

    expect(runChanges(changed, "default")).toEqual(["its layout", "its weather", "its equipment"]);
  });

  it("takes a layout the playback plays as its own", () => {
    const moved = "default~fan_right:-0.2:-2.9";

    expect(runChanges({ ...FOLLOWED, layout: moved }, moved)).toEqual([]);
    expect(runChanges(FOLLOWED, moved)).toEqual(["its layout"]);
  });

  it("takes the levels the run played back was given as its own commands (P13.8)", () => {
    const given = "129630:roof_vent:0.5";
    const drawn: ScenarioSource = {
      ...FOLLOWED,
      schedule: [{ timeS: 129_630, actuatorId: "roof_vent", level: 0.5 }],
    };

    expect(runChanges(drawn, "default", given)).toEqual([]);
    expect(runChanges(FOLLOWED, "default", given)).toEqual(["its commands"]);
    expect(runChanges(drawn, "default")).toEqual(["its commands"]);
  });

  it("goes back to the run played back with the levels it was given (P13.8)", () => {
    const given = [{ timeS: 129_630, actuatorId: "roof_vent", level: 0.5 }];
    const changed: ScenarioSource = {
      ...FOLLOWED,
      schedule: [{ timeS: 60, actuatorId: "heater", level: 1 }],
    };

    expect(withoutRunChanges(changed, "default", given)).toEqual({
      ...FOLLOWED,
      schedule: given,
    });
  });

  it("goes back to the run played back, keeping the view's own parts", () => {
    const changed: ScenarioSource = { ...FOLLOWED, weather: "cold", openings: { door: 1 } };

    expect(withoutRunChanges(changed, "default")).toEqual(FOLLOWED);
    expect(withoutRunChanges(changed, "default~fan_right:-0.2:-2.9")).toEqual({
      ...FOLLOWED,
      layout: "default~fan_right:-0.2:-2.9",
    });
  });
});
