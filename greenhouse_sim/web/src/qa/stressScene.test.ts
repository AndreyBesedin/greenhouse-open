import { describe, expect, it } from "vitest";

import { checkScene } from "../scene/checkScene";
import { loadScene, searchFor, sourceFromSearch } from "../scene/source";
import {
  DEFAULT_STRESS_PLANTS,
  MAX_STRESS_PLANTS,
  PAIR_SPACING_M,
  PLANT_PITCH_M,
  ROW_GAP_IN_PAIR_M,
  stressPlantPosition,
  stressPlants,
  stressScene,
} from "./stressScene";

describe("the stress scene", () => {
  it("holds the ground, the axes and the plants asked for, each named once", () => {
    const scene = stressScene(2_500);
    const ids = scene.entities.map((entity) => entity.entity_id);

    expect(scene.entities.filter((entity) => entity.kind === "PLANT")).toHaveLength(2_500);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toContain("stress_ground");
  });

  it("passes the scene check", () => {
    const scene = stressScene(250);

    expect(checkScene(scene)).toEqual({ ok: true, snapshot: scene });
  });

  it("is the same on every visit", () => {
    expect(stressScene(300)).toEqual(stressScene(300));
  });

  it("plants double rows, centred on the origin", () => {
    const rows = 4;
    const first = stressPlantPosition(0, 0, rows);
    const along = stressPlantPosition(1, 0, rows);
    const pairedRow = stressPlantPosition(0, 1, rows);
    const nextPair = stressPlantPosition(0, 2, rows);
    const last = stressPlantPosition(99, 3, rows);

    expect(along.x - first.x).toBeCloseTo(PLANT_PITCH_M);
    expect(pairedRow.y - first.y).toBeCloseTo(ROW_GAP_IN_PAIR_M);
    expect(nextPair.y - first.y).toBeCloseTo(PAIR_SPACING_M);
    expect(first.x + last.x).toBeCloseTo(0);
    expect(first.y + last.y).toBeCloseTo(0);
  });

  it("keeps every plant on the ground", () => {
    const scene = stressScene(1_000);
    const ground = scene.entities[0];
    if (ground?.shape.shape !== "plane") {
      throw new Error("the stress scene starts with its ground");
    }
    const { size_x, size_y } = ground.shape;
    const plants = scene.entities.filter((entity) => entity.kind === "PLANT");

    for (const plant of plants) {
      expect(Math.abs(plant.transform.position.x)).toBeLessThan(size_x / 2);
      expect(Math.abs(plant.transform.position.y)).toBeLessThan(size_y / 2);
    }
  });
});

describe("choosing the stress scene", () => {
  it.each([
    [null, DEFAULT_STRESS_PLANTS],
    ["500", 500],
    ["0", 1],
    ["999999", MAX_STRESS_PLANTS],
    ["lots", DEFAULT_STRESS_PLANTS],
  ])("reads plants=%j as %i plants", (value, plants) => {
    expect(stressPlants(value)).toBe(plants);
  });

  it("is kept in the address bar", () => {
    const source = sourceFromSearch("?scene=stress&plants=500");

    expect(source).toEqual({ kind: "stress", plants: 500 });
    expect(searchFor(source)).toBe("?scene=stress&plants=500");
  });

  it("is built in the viewer, with nothing to fetch", async () => {
    const nothing: typeof fetch = async () => {
      throw new Error("the stress scene should not be fetched");
    };

    const state = await loadScene({ kind: "stress", plants: 500 }, nothing);

    expect(state.status === "loaded" && state.snapshot.entities).toHaveLength(502);
  });
});
