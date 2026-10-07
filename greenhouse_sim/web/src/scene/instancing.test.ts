import { readFileSync } from "node:fs";

import { Matrix4, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import { MATRIX_SIZE, shapeBatches, shapeMatrices } from "./instancing";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
const PLANTS = EXAMPLE.entities.filter((entity) => entity.kind === "PLANT");
const [PLANT] = PLANTS as [SceneEntity];
const QUARTER_TURN = Math.SQRT1_2;

/** Where a point of the unit cylinder lands under instance `index`'s matrix. */
function placed(matrices: Float32Array, index: number, point: Vector3): Vector3 {
  const matrix = new Matrix4().fromArray(matrices, index * MATRIX_SIZE);
  return point.clone().applyMatrix4(matrix);
}

describe("instancing shapes", () => {
  it("gives each cylinder one matrix, in order", () => {
    expect(shapeMatrices(PLANTS)).toHaveLength(PLANTS.length * MATRIX_SIZE);
  });

  it("stands the unit cylinder where the entity stands, as wide and as tall", () => {
    const matrices = shapeMatrices([PLANT]);
    const top = placed(matrices, 0, new Vector3(0, 0, 1));
    const rim = placed(matrices, 0, new Vector3(1, 0, 0));
    const shape = PLANT.shape as { radius: number; height: number };

    expect(top.x).toBeCloseTo(0.5);
    expect(top.y).toBeCloseTo(1.6);
    expect(top.z).toBeCloseTo(shape.height);
    expect(rim.x).toBeCloseTo(0.5 + shape.radius);
    expect(rim.z).toBeCloseTo(0);
  });

  it("turns it as the entity is turned", () => {
    const tipped: SceneEntity = {
      ...PLANT,
      transform: { ...PLANT.transform, rotation: { w: QUARTER_TURN, x: QUARTER_TURN, y: 0, z: 0 } },
    };
    const top = placed(shapeMatrices([tipped]), 0, new Vector3(0, 0, 1));
    const shape = PLANT.shape as { height: number };

    expect(top.y).toBeCloseTo(1.6 - shape.height);
    expect(top.z).toBeCloseTo(0);
  });

  it("keeps a cylinder of zero height drawable", () => {
    const flat: SceneEntity = { ...PLANT, shape: { shape: "cylinder", radius: 0.02, height: 0 } };
    const matrix = new Matrix4().fromArray(shapeMatrices([flat]));

    expect(matrix.determinant()).not.toBe(0);
  });

  it("refuses an entity that is not a cylinder", () => {
    const floor = EXAMPLE.entities.find((entity) => entity.kind === "FLOOR") as SceneEntity;

    expect(() => shapeMatrices([floor])).toThrow(
      "gh_demo_floor is a plane, which is not drawn in batches",
    );
  });

  it("centres a sphere where the entity is, as wide as its radius", () => {
    const flower: SceneEntity = { ...PLANT, shape: { shape: "sphere", radius: 0.006 } };
    const matrices = shapeMatrices([flower]);
    const centre = placed(matrices, 0, new Vector3(0, 0, 0));
    const top = placed(matrices, 0, new Vector3(0, 0, 1));

    expect(centre.z).toBeCloseTo(0);
    expect(top.z).toBeCloseTo(0.006);
  });

  it("stretches an ellipsoid to its length, width and thickness", () => {
    const leaflet: SceneEntity = {
      ...PLANT,
      shape: { shape: "ellipsoid", size_x: 0.09, size_y: 0.045, size_z: 0.002 },
    };
    const matrices = shapeMatrices([leaflet]);
    // The unit ellipsoid is a sphere of diameter 1, so its tips are half a unit out.
    const tip = placed(matrices, 0, new Vector3(0.5, 0, 0));
    const edge = placed(matrices, 0, new Vector3(0, 0.5, 0));
    const face = placed(matrices, 0, new Vector3(0, 0, 0.5));

    expect(tip.x - 0.5).toBeCloseTo(0.045);
    expect(edge.y - 1.6).toBeCloseTo(0.0225);
    expect(face.z).toBeCloseTo(0.001);
  });

  it("batches by shape as well as by kind and finish", () => {
    const flower: SceneEntity = { ...PLANT, shape: { shape: "sphere", radius: 0.006 } };
    const batches = shapeBatches([PLANT, flower, PLANT]);

    expect(batches.map((batch) => [batch.batch, batch.shape, batch.entities.length])).toEqual([
      ["PLANT-cylinder-matt", "cylinder", 2],
      ["PLANT-sphere-matt", "sphere", 1],
    ]);
  });
});

describe("batching a layout's repeated fixtures", () => {
  // The canonical layout (`tests/test_scene_schema.py`).
  const QA_LAYOUT: SceneSnapshot = JSON.parse(
    readFileSync(new URL("../../public/scenes/qa-layout.json", import.meta.url), "utf8"),
  );

  it("draws every cylinder in one batch per kind and finish", () => {
    const cylinders = QA_LAYOUT.entities.filter((entity) => entity.shape.shape === "cylinder");
    const batches = shapeBatches(QA_LAYOUT.entities);

    // Planting positions, structural members, gutter legs, rail tubes,
    // heating pipes and crop wires: hundreds of cylinders, six draw calls.
    expect(new Set(batches.map((batch) => batch.batch))).toEqual(
      new Set([
        "PLANTING_POSITION-cylinder-matt",
        "FRAME-cylinder-metal",
        "CROP_GUTTER-cylinder-metal",
        "RAIL-cylinder-metal",
        "PIPE-cylinder-metal",
        "WIRE-cylinder-metal",
      ]),
    );
    expect(batches).toHaveLength(6);
    expect(cylinders.length).toBeGreaterThan(200);
    expect(batches.flatMap((batch) => batch.entities)).toHaveLength(cylinders.length);
  });
});
