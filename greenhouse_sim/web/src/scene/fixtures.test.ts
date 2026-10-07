import { readFileSync } from "node:fs";

import { Box3, type BufferGeometry, Matrix4, Quaternion, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import { shapeMatrices } from "./instancing";
import { solidGeometry } from "./ShapeMesh";

// The fixture gallery, as `tests/test_scene_schema.py` configures it, in its
// greenhouse's frame, whose corner stands at (-4, -2.4) in the world.
const GALLERY: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/qa-fixtures.json", import.meta.url), "utf8"),
);
const PIPE_RADIUS_M = 0.0255;
const RAIL_GAUGE_M = 0.55;
const WALKWAY_THICKNESS_M = 0.02;
const ORIGIN = { x: -4, y: -2.4 };

function fixture(name: string): SceneEntity {
  const entity = GALLERY.entities.find((each) => each.entity_id === `qa_fixtures_${name}`);
  if (entity === undefined) {
    throw new Error(`the gallery has no ${name}`);
  }
  return entity;
}

/** What the viewer draws for an entity, placed in the world: a cylinder as
 * its instanced batch draws it, a box as its mesh does. */
function drawn(entity: SceneEntity): BufferGeometry {
  const { shape, transform } = entity;
  if (shape.shape === "cylinder") {
    const unit = solidGeometry({ shape: "cylinder", radius: 1, height: 1 });
    return unit.applyMatrix4(new Matrix4().fromArray(shapeMatrices([entity])));
  }
  if (shape.shape !== "box") {
    throw new Error(`${entity.entity_id} is a ${shape.shape}`);
  }
  const { position, rotation } = transform;
  const matrix = new Matrix4().compose(
    new Vector3(position.x, position.y, position.z),
    new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w),
    new Vector3(1, 1, 1),
  );
  return solidGeometry(shape).applyMatrix4(matrix);
}

function size(geometry: BufferGeometry): Vector3 {
  geometry.computeBoundingBox();
  return (geometry.boundingBox ?? new Box3()).getSize(new Vector3());
}

function lowest(geometry: BufferGeometry): number {
  geometry.computeBoundingBox();
  return geometry.boundingBox?.min.z ?? Number.NaN;
}

/** Where a drawn cylinder's axis starts and ends, from its matrix. */
function axis(entity: SceneEntity): [Vector3, Vector3] {
  const matrix = new Matrix4().fromArray(shapeMatrices([entity]));
  return [new Vector3(0, 0, 0).applyMatrix4(matrix), new Vector3(0, 0, 1).applyMatrix4(matrix)];
}

function expectNear(actual: Vector3, expected: [number, number, number]): void {
  expect(actual.x).toBeCloseTo(expected[0], 6);
  expect(actual.y).toBeCloseTo(expected[1], 6);
  expect(actual.z).toBeCloseTo(expected[2], 6);
}

/** A point of the greenhouse's frame, in the world. */
function inWorld(x: number, y: number, z: number): [number, number, number] {
  return [ORIGIN.x + x, ORIGIN.y + y, z];
}

describe("the fixture gallery, as drawn", () => {
  it("stands the cabinet on the floor, 0.6 by 1.2 by 1.8 m", () => {
    const cabinet = drawn(fixture("cabinet"));

    expectNear(size(cabinet), [0.6, 1.2, 1.8]);
    expect(lowest(cabinet)).toBeCloseTo(0, 6);
  });

  it("stands the tank on the floor, 1 m across and 1.5 m tall", () => {
    const tank = drawn(fixture("tank"));

    expectNear(size(tank), [1.0, 1.0, 1.5]);
    expect(lowest(tank)).toBeCloseTo(0, 6);
  });

  it("runs the heating pipe from its start to its end, rising as it goes", () => {
    const [start, end] = axis(fixture("heating_pipe"));

    expectNear(start, inWorld(3.4, 0.6, 0.3));
    expectNear(end, inWorld(3.4, 4.2, 0.9));
    // Its rim stays one radius from its axis.
    const rim = new Vector3(1, 0, 0).applyMatrix4(
      new Matrix4().fromArray(shapeMatrices([fixture("heating_pipe")])),
    );
    expect(rim.distanceTo(start)).toBeCloseTo(PIPE_RADIUS_M, 6);
  });

  it("lays the rail's two tubes a gauge apart, either side of its centre line", () => {
    const [rightStart, rightEnd] = axis(fixture("pipe_rail_right"));
    const [leftStart, leftEnd] = axis(fixture("pipe_rail_left"));

    // Running along +y, its right is towards +x.
    expectNear(rightStart, inWorld(4.5 + RAIL_GAUGE_M / 2, 0.6, 0.1));
    expectNear(rightEnd, inWorld(4.5 + RAIL_GAUGE_M / 2, 4.2, 0.1));
    expectNear(leftStart, inWorld(4.5 - RAIL_GAUGE_M / 2, 0.6, 0.1));
    expectNear(leftEnd, inWorld(4.5 - RAIL_GAUGE_M / 2, 4.2, 0.1));
  });

  it("lays the crop gutter along its line, 0.3 m wide and 0.12 m deep", () => {
    const gutter = drawn(fixture("crop_gutter"));

    expectNear(size(gutter), [0.3, 3.6, 0.12]);
    expect(lowest(gutter)).toBeCloseTo(0, 6);
  });

  it("lays the walkway on the floor, 1.2 m wide and 4.2 m long", () => {
    const walkway = drawn(fixture("walkway"));

    expectNear(size(walkway), [1.2, 4.2, WALKWAY_THICKNESS_M]);
    expect(lowest(walkway)).toBeCloseTo(0, 6);
  });
});
