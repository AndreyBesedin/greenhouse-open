import { describe, expect, it } from "vitest";

import { cropAction, setLevel, setTarget } from "./plan";

describe("the actions the viewer asks of a run", () => {
  it("sets a device's level and a heating target as the protocol's actions", () => {
    expect(setLevel("vent_roof_1", 0.4)).toEqual({
      kind: "set_level",
      device_id: "vent_roof_1",
      level: 0.4,
    });
    expect(setTarget("heating_night", 17.5)).toEqual({
      kind: "set_target",
      target: "heating_night",
      value_c: 17.5,
    });
  });

  it("takes a plant's work as the protocol's action, as the plant lab names it", () => {
    const on = (
      kind: "remove_leaf" | "harvest_fruit" | "harvest_truss" | "lower_stem",
      target: string,
    ) => cropAction({ day: 3, plantId: "p30", kind, target });

    expect(on("remove_leaf", "p30_n02_leaf")).toEqual({
      kind: "remove_leaf",
      plant_id: "p30",
      leaf_id: "p30_n02_leaf",
    });
    expect(on("harvest_fruit", "p30_t03_f01")).toEqual({
      kind: "harvest",
      plant_id: "p30",
      scope: "fruit",
      organ_id: "p30_t03_f01",
    });
    expect(on("harvest_truss", "p30_t03")).toMatchObject({ scope: "truss", organ_id: "p30_t03" });
    expect(on("lower_stem", "1")).toEqual({ kind: "lower", plant_id: "p30", by_internodes: 1 });
  });
});
