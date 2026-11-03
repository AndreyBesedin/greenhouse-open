import { describe, expect, it } from "vitest";

import { FIRST_RUN, settingsOf } from "./RunStep";

describe("the settings the run step's fields hold (P17.11)", () => {
  it("are a run's, read as numbers", () => {
    expect(settingsOf({ ...FIRST_RUN, days: "30", seed: "4" })).toEqual({
      start_date: "2026-04-01",
      duration_days: 30,
      random_seed: 4,
      weather: "default",
    });
  });

  it.each([
    ["no date", { start: "" }],
    ["no days", { days: "" }],
    ["fewer than one day", { days: "0" }],
    ["a part of a day", { days: "1.5" }],
    ["no seed", { seed: "" }],
    ["a seed below 0", { seed: "-1" }],
    ["a part of a seed", { seed: "0.5" }],
  ])("are none with %s", (_, fields) => {
    expect(settingsOf({ ...FIRST_RUN, ...fields })).toBeNull();
  });
});
