import { describe, expect, it } from "vitest";

import { actionFrom, actionText, FIRST_LAB_RUN, labRunQuery } from "./lab";

describe("a scheduled action", () => {
  it("is written day:plant:action:organ, and read back", () => {
    const action = {
      day: 30,
      plantId: "p01",
      kind: "remove_leaf",
      target: "p01_n02_leaf",
    } as const;

    expect(actionText(action)).toBe("30:p01:remove_leaf:p01_n02_leaf");
    expect(actionFrom(actionText(action))).toEqual(action);
  });

  it("is not read from text that is not one", () => {
    for (const text of [
      "30:p01:remove_leaf",
      "soon:p01:remove_leaf:p01_n02_leaf",
      "30:p01:water:p01_n02_leaf",
      "30:p01:remove_leaf:p01_n02_leaf:again",
    ]) {
      expect(actionFrom(text)).toBeNull();
    }
  });

  it("is asked of the simulator's lab in the order scheduled", () => {
    const run = {
      ...FIRST_LAB_RUN,
      actions: [
        { day: 3, plantId: "p02", kind: "harvest_truss", target: "p02_t01" },
        { day: 4, plantId: "p02", kind: "lower_stem", target: "2" },
      ] as const,
    };

    expect(labRunQuery(run)).toBe(
      "day=0&seed=1&environment=reference&act=3%3Ap02%3Aharvest_truss%3Ap02_t01&act=4%3Ap02%3Alower_stem%3A2",
    );
  });
});
