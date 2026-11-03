import { describe, expect, it } from "vitest";

import { scenarioRun } from "../scene/run";
import type { SceneSource } from "../scene/source";
import { planKey, replaySource, withPlanOf } from "./replaySource";

const NO_PLAN = { targets: [], commands: [], crop: [] };

describe("the scene a replay draws", () => {
  it("is the scenario's own run when it has its own seed and layout", () => {
    expect(
      replaySource({ scenario_id: "climate_box", layout: "default", seed: null, ...NO_PLAN }),
    ).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      field: "climate",
    });
  });

  it("is asked for under its seed, which rides the weather's name", () => {
    const source = replaySource({
      scenario_id: "climate_box",
      layout: "default",
      seed: 7,
      ...NO_PLAN,
    });

    expect(source).toMatchObject({ weather: "default#7" });
    if (source.kind !== "scenario") {
      throw new Error("not a scenario");
    }
    expect(scenarioRun(source).weather).toBe("default#7");
  });

  it("keeps the layout a run was started with", () => {
    const source = replaySource({
      scenario_id: "climate_box",
      layout: "default~heater:-1.0:0.5",
      seed: null,
      ...NO_PLAN,
    });

    expect(source).toMatchObject({ layout: "default~heater:-1.0:0.5" });
  });
});

describe("a replay's plan", () => {
  const own = { scenario_id: "box", layout: "default", seed: null };
  const none = { targets: [], commands: [], crop: [] };
  const planned = {
    targets: [[60, "heating_day", 23]] as [number, string, number][],
    commands: [[120, "heater", 0.5]] as [number, string, number][],
    crop: [[86_400, "p1", "harvest_truss", "t1"]] as [number, string, string, string][],
  };

  it("draws the epoch under the changes given to it", () => {
    expect(replaySource({ ...own, ...planned })).toMatchObject({
      targets: [{ timeS: 60, target: "heating_day", valueC: 23 }],
      schedule: [{ timeS: 120, actuatorId: "heater", level: 0.5 }],
      crop: [{ timeS: 86_400, plantId: "p1", kind: "harvest_truss", target: "t1" }],
    });
    const plain = replaySource({ ...own, ...none });
    expect(plain).not.toHaveProperty("targets");
    expect(plain).not.toHaveProperty("schedule");
    expect(plain).not.toHaveProperty("crop");
  });

  it("follows a plan that grows, keeping what the viewer chose", () => {
    const shown = { ...replaySource({ ...own, ...none }), time: 7 } as SceneSource;
    const grown = replaySource({ ...own, ...planned });

    const next = withPlanOf(shown, grown);

    expect(next).toMatchObject({ time: 7, schedule: [{ actuatorId: "heater" }] });
    // Nothing to change, and the same scene: no request made again.
    expect(withPlanOf(next, grown)).toBe(next);
  });

  it("has a key that changes with the plan", () => {
    expect(planKey(none)).not.toBe(planKey(planned));
  });
});
