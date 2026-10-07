import { describe, expect, it } from "vitest";

import type { SceneEntity } from "../scene/generated/snapshotTypes";
import { actionsFor } from "./PlantActions";

function organ(properties: SceneEntity["properties"]): SceneEntity {
  return {
    entity_id: "x",
    kind: "LEAF",
    transform: { position: { x: 0, y: 0, z: 0 }, rotation: { w: 1, x: 0, y: 0, z: 0 } },
    shape: { shape: "sphere", radius: 0.01 },
    color: { r: 0, g: 0, b: 0 },
    properties,
  } as SceneEntity;
}

describe("what can be done to a selected organ's plant", () => {
  it("prunes a leaf, or lowers its stem", () => {
    const leaf = organ({ organ_id: "p01_n02_leaf", organ_kind: "leaf", plant_id: "p01" });

    expect(
      actionsFor(leaf, 30).map(({ label, action }) => [label, action.kind, action.target]),
    ).toEqual([
      ["Remove this leaf", "remove_leaf", "p01_n02_leaf"],
      ["Lower the stem", "lower_stem", "1"],
    ]);
  });

  it("picks a fruit or cuts its truss, on the day on show", () => {
    const fruit = organ({
      organ_id: "p01_t02_fr03",
      organ_kind: "fruit",
      plant_id: "p01",
      truss_id: "p01_t02",
    });
    const choices = actionsFor(fruit, 85);

    expect(choices.map(({ action }) => action.kind)).toEqual([
      "harvest_fruit",
      "harvest_truss",
      "lower_stem",
    ]);
    expect(choices[1]?.action).toEqual({
      day: 85,
      plantId: "p01",
      kind: "harvest_truss",
      target: "p01_t02",
    });
  });

  it("offers nothing for what is not part of a plant", () => {
    expect(actionsFor(organ({}), 0)).toEqual([]);
  });
});
