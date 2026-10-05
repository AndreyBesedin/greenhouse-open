import { Matrix4, Quaternion, Vector3 } from "three";

import type { SceneEntity } from "./generated/snapshotTypes";

export const MATRIX_SIZE = 16;
// A cylinder of zero height is drawn this tall, so that its matrix stays
// invertible and its lighting defined; at a tenth of a millimetre it still
// reads as a disc on the ground.
const LEAST_DRAWN_HEIGHT_M = 0.0001;

/**
 * Each cylinder's placement as a 4x4 matrix, column-major as Three.js stores
 * them: its transform, scaled to its radius and height. The matrices place a
 * unit cylinder (radius 1, height 1) standing on its frame's origin along +z,
 * as `world/geometry.py` stands a cylinder.
 */
export function cylinderMatrices(entities: readonly SceneEntity[]): Float32Array {
  const matrices = new Float32Array(entities.length * MATRIX_SIZE);
  const matrix = new Matrix4();
  const position = new Vector3();
  const rotation = new Quaternion();
  const scale = new Vector3();
  entities.forEach((entity, index) => {
    const { shape, transform } = entity;
    if (shape.shape !== "cylinder") {
      throw new Error(`${entity.entity_id} is a ${shape.shape}, not a cylinder`);
    }
    const { x, y, z } = transform.position;
    const turn = transform.rotation;
    matrix.compose(
      position.set(x, y, z),
      rotation.set(turn.x, turn.y, turn.z, turn.w),
      scale.set(shape.radius, shape.radius, Math.max(shape.height, LEAST_DRAWN_HEIGHT_M)),
    );
    matrix.toArray(matrices, index * MATRIX_SIZE);
  });
  return matrices;
}
