import { describe, expect, it } from "vitest";

import { scenarioRun } from "../scene/run";
import { replaySource } from "./replaySource";

describe("the scene a replay draws", () => {
  it("is the scenario's own run when it has its own seed and layout", () => {
    expect(replaySource({ scenario_id: "climate_box", layout: "default", seed: null })).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      field: "climate",
    });
  });

  it("is asked for under its seed, which rides the weather's name", () => {
    const source = replaySource({ scenario_id: "climate_box", layout: "default", seed: 7 });

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
    });

    expect(source).toMatchObject({ layout: "default~heater:-1.0:0.5" });
  });
});
