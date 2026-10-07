import { describe, expect, it } from "vitest";

import { loadPlantStructure, type OrganNode, organTree } from "./structure";

// A plant of one phytomer with a truss of two flowers, one set as a fruit, as
// the simulator's plant lab writes it.
const PLANT = {
  born_tt: 0,
  plant_id: "p01",
  thermal_time: 100,
  stem: {
    born_tt: 0,
    axis_id: "p01_stem",
    phytomers: [
      {
        born_tt: 0,
        phytomer_id: "p01_n01",
        rank: 1,
        internode: { born_tt: 0, internode_id: "p01_n01_internode", length_cm: 5, diameter_mm: 8 },
        leaf: { born_tt: 0, leaf_id: "p01_n01_leaf", length_cm: 20, stage: "mature" },
        truss: {
          born_tt: 40,
          truss_id: "p01_t01",
          number: 1,
          final_flower_count: 3,
          flowers: [
            {
              born_tt: 40,
              flower_id: "p01_t01_fl01",
              rank: 1,
              stage: "set",
              fruit: {
                born_tt: 70,
                fruit_id: "p01_t01_fr01",
                diameter_mm: 4,
                stage: "growing",
              },
            },
            { born_tt: 45, flower_id: "p01_t01_fl02", rank: 2, stage: "bud", fruit: null },
            {
              born_tt: 50,
              flower_id: "p01_t01_fl03",
              rank: 3,
              stage: "set",
              fruit: { born_tt: 80, fruit_id: "p01_t01_fr03", diameter_mm: 6, stage: "aborted" },
            },
          ],
        },
      },
    ],
  },
};

function flatten(node: OrganNode): OrganNode[] {
  return [node, ...node.children.flatMap(flatten)];
}

function answering(status: number, body: unknown): typeof fetch {
  return async () => new Response(JSON.stringify(body), { status });
}

describe("a plant's structure", () => {
  it("is a tree from the plant down, each organ under the one it is attached to", () => {
    const tree = organTree(PLANT);

    expect(flatten(tree).map((node) => `${node.kind} ${node.id}`)).toEqual([
      "plant p01",
      "stem p01_stem",
      "phytomer p01_n01",
      "internode p01_n01_internode",
      "leaf p01_n01_leaf",
      "truss p01_t01",
      "flower p01_t01_fl01",
      "fruit p01_t01_fr01",
      "flower p01_t01_fl02",
      "flower p01_t01_fl03",
      "fruit p01_t01_fr03",
    ]);
  });

  it("says how far each organ has developed, and its stage", () => {
    const organs = Object.fromEntries(flatten(organTree(PLANT)).map((node) => [node.id, node]));

    expect(organs.p01_n01_leaf?.detail).toBe("100 °Cd, mature");
    expect(organs.p01_t01_fr01?.detail).toBe("30 °Cd, growing");
    expect(organs.p01_n01?.detail).toBe("100 °Cd");
  });

  it("marks the organs the view draws: not a set flower, but its fruit, unless it aborted", () => {
    const organs = Object.fromEntries(flatten(organTree(PLANT)).map((node) => [node.id, node]));

    expect(organs.p01_t01_fl01?.drawn).toBe(false);
    expect(organs.p01_t01_fr01?.drawn).toBe(true);
    expect(organs.p01_t01_fl02?.drawn).toBe(true);
    expect(organs.p01_t01_fl03?.drawn).toBe(false);
    expect(organs.p01_t01_fr03?.drawn).toBe(false);
    expect(organs.p01_stem?.drawn).toBe(false);
  });

  it("refuses a structure it cannot read", () => {
    expect(() => organTree({ plant_id: "p01", thermal_time: 1 })).toThrow("the stem");
    expect(() => organTree({ ...PLANT, stem: { ...PLANT.stem, phytomers: {} } })).toThrow(
      "phytomers is not a list",
    );
  });

  it("is loaded from the plant lab by plant, day and seed, and an error becomes unavailable", async () => {
    const asked: string[] = [];
    const recording: typeof fetch = async (input) => {
      asked.push(String(input));
      return new Response(JSON.stringify(PLANT), { status: 200 });
    };
    const loaded = await loadPlantStructure({ plantId: "p07", day: 12, seed: 3 }, recording);
    const refused = await loadPlantStructure(
      { plantId: "p01", day: 0, seed: 1 },
      answering(502, { error: "bad gateway" }),
    );

    expect(asked).toEqual(["/api/plants/structure?day=12&seed=3&plant=p07"]);
    expect(loaded.status).toBe("loaded");
    expect(refused).toEqual({ status: "unavailable", reason: "the simulator API answered 502" });
  });
});
