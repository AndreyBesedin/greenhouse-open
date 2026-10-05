import { readFileSync } from "node:fs";

import { Matrix4, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import { cylinderMatrices, MATRIX_SIZE } from "./instancing";

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

describe("instancing cylinders", () => {
  it("gives each cylinder one matrix, in order", () => {
    expect(cylinderMatrices(PLANTS)).toHaveLength(PLANTS.length * MATRIX_SIZE);
  });

  it("stands the unit cylinder where the entity stands, as wide and as tall", () => {
    const matrices = cylinderMatrices([PLANT]);
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
    const top = placed(cylinderMatrices([tipped]), 0, new Vector3(0, 0, 1));
    const shape = PLANT.shape as { height: number };

    expect(top.y).toBeCloseTo(1.6 - shape.height);
    expect(top.z).toBeCloseTo(0);
  });

  it("keeps a cylinder of zero height drawable", () => {
    const flat: SceneEntity = { ...PLANT, shape: { shape: "cylinder", radius: 0.02, height: 0 } };
    const matrix = new Matrix4().fromArray(cylinderMatrices([flat]));

    expect(matrix.determinant()).not.toBe(0);
  });

  it("refuses an entity that is not a cylinder", () => {
    const ground = EXAMPLE.entities.find((entity) => entity.kind === "GROUND") as SceneEntity;

    expect(() => cylinderMatrices([ground])).toThrow("gh_demo_ground is a plane, not a cylinder");
  });
});
