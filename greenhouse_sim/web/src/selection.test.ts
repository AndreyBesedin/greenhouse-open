import { readFileSync } from "node:fs";

import { Group, InstancedMesh, Mesh } from "three";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { entityOfOrgan, highlighted, organOf, pickEntity, selectedEntity } from "./selection";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/example.json", import.meta.url), "utf8"),
);

function drawnEntity(entityId: string, kind = "PLANT"): { group: Group; mesh: Mesh } {
  const group = new Group();
  group.userData.entityId = entityId;
  group.userData.entityKind = kind;
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

describe("picking through glass", () => {
  it("reaches a solid entity behind it, and picks the glass only with nothing behind", () => {
    const wall = drawnEntity("gh_demo_side_wall_right");
    wall.mesh.userData.seeThrough = true;
    const plant = drawnEntity("gh_demo_plant_001");

    expect(pickEntity([{ object: wall.mesh }, { object: plant.mesh }])).toBe("gh_demo_plant_001");
    expect(pickEntity([{ object: wall.mesh }])).toBe("gh_demo_side_wall_right");
  });
});

describe("picking a zone", () => {
  it("picks the zone over the floor it stands on, but not over what stands in it", () => {
    const zone = drawnEntity("gh_001_keep_out_irrigation", "KEEP_OUT");
    zone.mesh.userData.seeThrough = true;
    const floor = drawnEntity("gh_001_floor", "FLOOR");
    const unit = drawnEntity("gh_001_irrigation_unit", "OBSTACLE");
    const roof = drawnEntity("gh_001_roof_2_right", "ROOF");
    roof.mesh.userData.seeThrough = true;

    expect(pickEntity([{ object: roof.mesh }, { object: zone.mesh }, { object: floor.mesh }])).toBe(
      "gh_001_keep_out_irrigation",
    );
    expect(pickEntity([{ object: zone.mesh }, { object: unit.mesh }, { object: floor.mesh }])).toBe(
      "gh_001_irrigation_unit",
    );
    // Through the glass, without a zone, the floor.
    expect(pickEntity([{ object: roof.mesh }, { object: floor.mesh }])).toBe("gh_001_floor");
  });
});

describe("picking an instance of a batch", () => {
  it("names the entity drawn as that instance", () => {
    const batch = new InstancedMesh(undefined, undefined, 3);
    batch.userData.entityIds = ["gh_demo_plant_001", "gh_demo_plant_002", "gh_demo_plant_003"];

    expect(pickEntity([{ object: batch, instanceId: 1 }])).toBe("gh_demo_plant_002");
    expect(pickEntity([{ object: batch, instanceId: 7 }])).toBeNull();
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

describe("selecting part of an organ", () => {
  // Two parts of one leaf, and an internode, as the plant lab draws them.
  const [plant] = EXAMPLE.entities.filter((entity) => entity.kind === "PLANT");
  const part = (entityId: string, organId: string) => ({
    ...(plant as SceneSnapshot["entities"][number]),
    entity_id: entityId,
    properties: { organ_id: organId },
  });
  const LAB: SceneSnapshot = {
    ...EXAMPLE,
    entities: [
      part("p01_n01_internode", "p01_n01_internode"),
      part("p01_n01_leaf_petiole", "p01_n01_leaf"),
      part("p01_n01_leaf_terminal", "p01_n01_leaf"),
    ],
  };

  it("highlights every part of the organ, and only the entity otherwise", () => {
    expect(highlighted(LAB, "p01_n01_leaf_terminal")).toEqual(
      new Set(["p01_n01_leaf_petiole", "p01_n01_leaf_terminal"]),
    );
    expect(highlighted(LAB, "p01_n01_internode")).toEqual(new Set(["p01_n01_internode"]));
    expect(highlighted(EXAMPLE, "gh_demo_plant_002")).toEqual(new Set(["gh_demo_plant_002"]));
    expect(highlighted(LAB, null)).toEqual(new Set());
  });

  it("names the organ an entity draws, and finds an organ's first part", () => {
    expect(organOf(LAB.entities[2] as SceneSnapshot["entities"][number])).toBe("p01_n01_leaf");
    expect(organOf(plant as SceneSnapshot["entities"][number])).toBeNull();
    expect(entityOfOrgan(LAB, "p01_n01_leaf")).toBe("p01_n01_leaf_petiole");
    expect(entityOfOrgan(LAB, "p01_n09_leaf")).toBeNull();
    expect(entityOfOrgan(null, "p01_n01_leaf")).toBeNull();
  });
});
