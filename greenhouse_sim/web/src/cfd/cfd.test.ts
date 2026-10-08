import { describe, expect, it } from "vitest";

import { boundaryOutlines, boundaryShape, categorySummary } from "./boundaries";
import { describeState } from "./CfdControls";
import type { Boundary, CfdGeometry, Face } from "./generated/geometryTypes";
import { cfdGeometryUrl, checkCfdGeometry, loadCfdGeometry } from "./geometry";

const point = (x: number, y: number, z: number) => ({ x, y, z });

function face(name: string, category: Boundary["category"], face: Face): Boundary {
  const top = face === "ceiling" ? 3 : 0;
  return {
    name,
    category,
    face,
    box: { minimum: point(0, 0, top), maximum: point(4, 2, top) },
    mesh_faces: 32,
  };
}

// A domain 4 by 2 by 3 m in cells of 0.5 m, with only a floor, a ceiling and
// a vent in it, and one obstacle on the floor: enough to draw.
const GEOMETRY: CfdGeometry = {
  schema_version: 1,
  scenario_id: "box",
  grid: { origin: point(0, 0, 0), cell_size: point(0.5, 0.5, 0.5), cells: point(8, 4, 6) },
  boundaries: [
    face("floor", "floor", "floor"),
    face("ceiling", "ceiling", "ceiling"),
    {
      name: "roof_vent_1",
      category: "opening",
      face: "ceiling",
      opening_id: "roof_vent_1",
      opening_kind: "roof_vent",
      box: { minimum: point(1, 0.5, 3), maximum: point(2, 1, 3) },
      mesh_faces: 2,
    },
    {
      name: "obstacle_tank",
      category: "obstacle",
      box: { minimum: point(3, 0, 0), maximum: point(3.5, 1, 1.5) },
      mesh_faces: 6,
    },
  ],
  too_small: ["slab_1", "slab_2"],
  unplaced: [],
};

describe("a CFD geometry from the simulator", () => {
  it("is checked against the schema the simulator publishes", () => {
    const { scenario_id: _, ...nameless } = GEOMETRY;

    expect(checkCfdGeometry(GEOMETRY)).toEqual({ ok: true, geometry: GEOMETRY });
    expect(checkCfdGeometry(nameless)).toMatchObject({
      ok: false,
      problems: ["the geometry must have required property 'scenario_id'"],
    });
    expect(checkCfdGeometry({ ...GEOMETRY, schema_version: 2 }).ok).toBe(false);
  });

  it("is asked for changed as the scene is, and its failures are states to show", async () => {
    const url = cfdGeometryUrl("tomato_compartment", "?open=door_1:1");
    const asked: string[] = [];
    const loaded = await loadCfdGeometry(url, async (input) => {
      asked.push(String(input));
      return new Response(JSON.stringify(GEOMETRY), { status: 200 });
    });
    const missing = await loadCfdGeometry(url, async () => new Response("", { status: 404 }));
    const refused = await loadCfdGeometry(
      url,
      async () => new Response(JSON.stringify({ ...GEOMETRY, boundaries: 3 }), { status: 200 }),
    );

    expect(asked).toEqual(["/api/scenarios/tomato_compartment/cfd/geometry?open=door_1:1"]);
    expect(loaded).toEqual({ status: "loaded", geometry: GEOMETRY });
    expect(missing).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 404",
    });
    expect(refused.status).toBe("rejected");
  });
});

describe("drawing a CFD geometry's boundaries", () => {
  it("draws each face just inside the domain, and an opening just outside it", () => {
    const [floor, ceiling, vent, tank] = GEOMETRY.boundaries.map(boundaryShape);

    expect(floor).toMatchObject({ normal: "z", centre: { x: 2, y: 1, z: 0.02 } });
    expect(ceiling).toMatchObject({ normal: "z", centre: { z: 2.98 } });
    expect(vent).toMatchObject({ normal: "z", centre: { x: 1.5, y: 0.75, z: 3.03 } });
    expect(tank).toMatchObject({
      normal: null,
      centre: { x: 3.25, y: 0.5, z: 0.75 },
      size: { x: 0.5, y: 1, z: 1.5 },
    });
  });

  it("outlines a flat boundary by its four edges and a box by its twelve", () => {
    const [floor, , , tank] = GEOMETRY.boundaries.map(boundaryShape);
    const SEGMENT = 6;
    if (floor === undefined || tank === undefined) {
      throw new Error("the geometry has a floor and an obstacle");
    }
    const flat = boundaryOutlines([floor]);
    const box = boundaryOutlines([tank]);
    // Every edge is a whole side, along one axis.
    const lengths = Array.from({ length: box.positions.length / SEGMENT }, (_, i) => {
      const [x0, y0, z0, x1, y1, z1] = box.positions.slice(i * SEGMENT, (i + 1) * SEGMENT);
      return Math.hypot((x1 ?? 0) - (x0 ?? 0), (y1 ?? 0) - (y0 ?? 0), (z1 ?? 0) - (z0 ?? 0));
    });

    expect(flat.positions.length / SEGMENT).toBe(4);
    // All at the floor's height, in 32-bit floats.
    expect(new Set(flat.positions.filter((_, i) => i % 3 === 2))).toEqual(
      new Set([Math.fround(0.02)]),
    );
    expect(lengths.sort()).toEqual([0.5, 0.5, 0.5, 0.5, 1, 1, 1, 1, 1.5, 1.5, 1.5, 1.5]);
    expect(box.colors.length).toBe(box.positions.length);
  });

  it("sums each category's boundaries and faces in the legend's order, and says what it drew", () => {
    expect(categorySummary(GEOMETRY)).toEqual([
      { category: "floor", boundaries: 1, meshFaces: 32 },
      { category: "ceiling", boundaries: 1, meshFaces: 32 },
      { category: "opening", boundaries: 1, meshFaces: 2 },
      { category: "obstacle", boundaries: 1, meshFaces: 6 },
    ]);
    expect(describeState({ status: "loaded", geometry: GEOMETRY })).toBe(
      "8 × 4 × 6 cells, 1 opening, 1 obstacle removing 6 cells; 2 fixtures too small to remove a cell.",
    );
    expect(
      describeState({ status: "loaded", geometry: { ...GEOMETRY, unplaced: ["door_1"] } }),
    ).toMatch(/; no face left for door_1\.$/);
  });
});
