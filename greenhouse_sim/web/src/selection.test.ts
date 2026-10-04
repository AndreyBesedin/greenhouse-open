import { readFileSync } from "node:fs";

import { Group, Mesh } from "three";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { pickEntity, selectedEntity } from "./selection";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/example.json", import.meta.url), "utf8"),
);

function drawnEntity(entityId: string): { group: Group; mesh: Mesh } {
  const group = new Group();
  group.userData.entityId = entityId;
  const mesh = new Mesh();
  group.add(mesh);
  return { group, mesh };
}

describe("picking an entity", () => {
  it("takes the nearest hit that is part of an entity", () => {
    const plant = drawnEntity("gh_demo_plant_001");
    const ground = drawnEntity("gh_demo_ground");

    expect(pickEntity([{ object: plant.mesh }, { object: ground.mesh }])).toBe("gh_demo_plant_001");
    expect(pickEntity([{ object: ground.mesh }, { object: plant.mesh }])).toBe("gh_demo_ground");
  });

  it("looks past hits that belong to no entity, and finds none without one", () => {
    const ground = drawnEntity("gh_demo_ground");
    const pointerPlane = new Mesh();

    expect(pickEntity([{ object: pointerPlane }, { object: ground.mesh }])).toBe("gh_demo_ground");
    expect(pickEntity([{ object: pointerPlane }])).toBeNull();
    expect(pickEntity([])).toBeNull();
  });
});

describe("a selection", () => {
  it("follows its entity into the next scene", () => {
    const nextDay: SceneSnapshot = {
      ...EXAMPLE,
      simulated_day: EXAMPLE.simulated_day + 1,
      entities: EXAMPLE.entities.map((entity) => ({
        ...entity,
        properties: { ...entity.properties, age_days: EXAMPLE.simulated_day + 1 },
      })),
    };

    const before = selectedEntity(EXAMPLE, "gh_demo_plant_002");
    const after = selectedEntity(nextDay, "gh_demo_plant_002");

    expect(before?.properties.age_days).toBe(EXAMPLE.simulated_day);
    expect(after?.entity_id).toBe("gh_demo_plant_002");
    expect(after?.properties.age_days).toBe(EXAMPLE.simulated_day + 1);
  });

  it("is nothing without a scene, or when the scene has no such entity", () => {
    expect(selectedEntity(null, "gh_demo_plant_002")).toBeNull();
    expect(selectedEntity(EXAMPLE, null)).toBeNull();
    expect(selectedEntity(EXAMPLE, "gh_demo_plant_999")).toBeNull();
  });
});
