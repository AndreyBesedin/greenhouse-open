import { Matrix4, Quaternion, Vector3 } from "three";

import type { Cylinder, Ellipsoid, SceneEntity, Sphere } from "./generated/snapshotTypes";
import { isMetal } from "./materials";

export const MATRIX_SIZE = 16;
// A cylinder of zero height is drawn this tall, so that its matrix stays
// invertible and its lighting defined; at a tenth of a millimetre it still
// reads as a disc on the ground.
const LEAST_DRAWN_HEIGHT_M = 0.0001;

/** The shapes repeated by the hundred, which are drawn in instanced batches. */
export type InstancedShape = Cylinder | Sphere | Ellipsoid;
export type InstancedShapeName = InstancedShape["shape"];

const INSTANCED: ReadonlySet<string> = new Set<InstancedShapeName>([
  "cylinder",
  "sphere",
  "ellipsoid",
]);

/** The unit shape each instance is a placed and scaled copy of. */
export const UNIT_SHAPES: Record<InstancedShapeName, InstancedShape> = {
  cylinder: { shape: "cylinder", radius: 1, height: 1 },
  sphere: { shape: "sphere", radius: 1 },
  ellipsoid: { shape: "ellipsoid", size_x: 1, size_y: 1, size_z: 1 },
};

export function isInstanced(entity: SceneEntity): boolean {
  return INSTANCED.has(entity.shape.shape);
}

/** Shapes drawn in one instanced batch: of one kind, one shape, and one
 * finish. */
export interface ShapeBatch {
  /** The kind, shape and finish, such as `PIPE-cylinder-metal`. */
  batch: string;
  shape: InstancedShapeName;
  metallic: boolean;
  entities: SceneEntity[];
}

/** A scene's cylinders, spheres and ellipsoids, grouped by kind, by shape and
 * by finish (metal or not), each group in scene order: every group is drawn
 * as one instanced batch. */
export function shapeBatches(entities: readonly SceneEntity[]): ShapeBatch[] {
  const batches = new Map<string, ShapeBatch>();
  for (const entity of entities) {
    if (!isInstanced(entity)) {
      continue;
    }
    const shape = entity.shape.shape as InstancedShapeName;
    const metallic = isMetal(entity);
    const key = `${entity.kind}-${shape}-${metallic ? "metal" : "matt"}`;
    const batch = batches.get(key) ?? { batch: key, shape, metallic, entities: [] };
    batch.entities.push(entity);
    batches.set(key, batch);
  }
  return [...batches.values()];
}

/** How far an instance stretches its unit shape along x, y and z. */
function stretch(entity: SceneEntity, scale: Vector3): Vector3 {
  const { shape } = entity;
  switch (shape.shape) {
    case "cylinder":
      return scale.set(shape.radius, shape.radius, Math.max(shape.height, LEAST_DRAWN_HEIGHT_M));
    case "sphere":
      return scale.set(shape.radius, shape.radius, shape.radius);
    case "ellipsoid":
      return scale.set(shape.size_x, shape.size_y, shape.size_z);
    default:
      throw new Error(`${entity.entity_id} is a ${shape.shape}, which is not drawn in batches`);
  }
}

/**
 * Each shape's placement as a 4x4 matrix, column-major as Three.js stores
 * them: its transform, scaled to its size. The matrices place the shape's unit
 * copy (`UNIT_SHAPES`) where `world/geometry.py` places the shape: a cylinder
 * standing on its frame's origin along +z, a sphere or ellipsoid centred on it.
 */
export function shapeMatrices(entities: readonly SceneEntity[]): Float32Array {
  const matrices = new Float32Array(entities.length * MATRIX_SIZE);
  const matrix = new Matrix4();
  const position = new Vector3();
  const rotation = new Quaternion();
  const scale = new Vector3();
  entities.forEach((entity, index) => {
    const { x, y, z } = entity.transform.position;
    const turn = entity.transform.rotation;
    matrix.compose(
      position.set(x, y, z),
      rotation.set(turn.x, turn.y, turn.z, turn.w),
      stretch(entity, scale),
    );
    matrix.toArray(matrices, index * MATRIX_SIZE);
  });
  return matrices;
}
