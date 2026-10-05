import { describe, expect, it } from "vitest";

import { checkScene } from "../scene/checkScene";
import { DEFAULT_QA_SEED, QA_COLOUR_PROPERTY, QA_SELECTED_ID, qaSeed } from "./qaPage";
import { qaScene, seededRandom } from "./qaScene";

const SEEDS = [0, 1, DEFAULT_QA_SEED, 2 ** 31, 4294967295];

describe("the renderer's QA scene", () => {
  it.each(SEEDS)("passes the scene check for seed %i", (seed) => {
    expect(checkScene(qaScene(seed))).toEqual({ ok: true, snapshot: qaScene(seed) });
  });

  it("is the same for the same seed, and different for another", () => {
    const heights = (seed: number) =>
      qaScene(seed).entities.map((entity) =>
        entity.shape.shape === "cylinder" ? entity.shape.height : null,
      );

    expect(qaScene(DEFAULT_QA_SEED)).toEqual(qaScene(DEFAULT_QA_SEED));
    expect(heights(DEFAULT_QA_SEED + 1)).not.toEqual(heights(DEFAULT_QA_SEED));
  });

  it("has the ground, the axes and fifteen leaning plants, each named once", () => {
    const scene = qaScene(DEFAULT_QA_SEED);
    const kinds = scene.entities.map((entity) => entity.kind);
    const ids = scene.entities.map((entity) => entity.entity_id);

    expect(kinds.filter((kind) => kind === "PLANT")).toHaveLength(15);
    expect(kinds).toContain("GROUND");
    expect(kinds).toContain("AXES");
    expect(new Set(ids).size).toBe(ids.length);
    const plants = scene.entities.filter((entity) => entity.kind === "PLANT");
    expect(plants.every((plant) => plant.transform.rotation.w < 1)).toBe(true);
  });

  it("holds the plant the page selects and the property it colours by", () => {
    const selected = qaScene(DEFAULT_QA_SEED).entities.find(
      (entity) => entity.entity_id === QA_SELECTED_ID,
    );

    expect(typeof selected?.properties[QA_COLOUR_PROPERTY]).toBe("number");
  });
});

describe("the seeded numbers", () => {
  it("repeat for a seed and stay in [0, 1)", () => {
    const first = seededRandom(7);
    const second = seededRandom(7);
    const numbers = Array.from({ length: 1000 }, () => first());

    expect(Array.from({ length: 1000 }, () => second())).toEqual(numbers);
    expect(numbers.every((value) => value >= 0 && value < 1)).toBe(true);
    expect(new Set(numbers).size).toBe(numbers.length);
  });
});

describe("the QA page's address", () => {
  it.each([
    ["", DEFAULT_QA_SEED],
    ["?seed=7", 7],
    ["?seed=0", 0],
    ["?seed=-1", null],
    ["?seed=4.2", null],
    ["?seed=abc", null],
  ])("reads %j as seed %s", (search, seed) => {
    expect(qaSeed(search)).toBe(seed);
  });
});
