import { Box3, Quaternion, Vector3 } from "three";

import type { SceneEntity, Shape } from "../scene/generated/snapshotTypes";
import type { Point3 } from "../world";

/** A world-aligned box, in metres. */
export interface Bounds {
  min: Point3;
  max: Point3;
}

/**
 * Debug drawing in world coordinates (metres, z up), independent of what it
 * explains: the selection today, and later airflow, radiation, sensors or
 * plants. `Overlays` draws any list of them; `id` is unique within a list.
 */
export type OverlayPrimitive = { id: string } & (
  | { kind: "point"; position: Point3; color: string }
  | { kind: "arrow"; origin: Point3; direction: Point3; length: number; color: string }
  | { kind: "box"; bounds: Bounds; color: string }
  | { kind: "line"; from: Point3; to: Point3; color: string }
  | { kind: "label"; position: Point3; text: string }
);

/** Which overlays are drawn around the selected entity. */
export interface OverlayToggles {
  box: boolean;
  axes: boolean;
  label: boolean;
}

export const ALL_OVERLAYS: OverlayToggles = { box: true, axes: true, label: true };

export const SELECTION_COLOR = "#ff8c1a";
// The entity's own axes, coloured as the world axes are: x red, y green, z blue.
const FRAME_AXES: readonly { name: string; axis: Point3; color: string }[] = [
  { name: "x", axis: { x: 1, y: 0, z: 0 }, color: "#e03c31" },
  { name: "y", axis: { x: 0, y: 1, z: 0 }, color: "#2e9e44" },
  { name: "z", axis: { x: 0, y: 0, z: 1 }, color: "#2f6fd6" },
];
// Long enough to read beside a plant, short enough to stay near it.
const FRAME_ARROW_LENGTH_M = 0.3;
// How far above the entity its label floats, on a leader line.
const LABEL_RISE_M = 0.15;

function point(vector: Vector3): Point3 {
  return { x: vector.x, y: vector.y, z: vector.z };
}

/** The box a shape fills in its own frame, as `world/geometry.py` describes it. */
function shapeExtent(shape: Shape): Bounds {
  switch (shape.shape) {
    case "plane":
      return {
        min: { x: -shape.size_x / 2, y: -shape.size_y / 2, z: 0 },
        max: { x: shape.size_x / 2, y: shape.size_y / 2, z: 0 },
      };
    case "cylinder":
      return {
        min: { x: -shape.radius, y: -shape.radius, z: 0 },
        max: { x: shape.radius, y: shape.radius, z: shape.height },
      };
    case "box":
      return {
        min: { x: -shape.size_x / 2, y: -shape.size_y / 2, z: 0 },
        max: { x: shape.size_x / 2, y: shape.size_y / 2, z: shape.size_z },
      };
    case "polygon": {
      const xs = shape.points.map((point) => point.x);
      const ys = shape.points.map((point) => point.y);
      return {
        min: { x: Math.min(...xs), y: Math.min(...ys), z: 0 },
        max: { x: Math.max(...xs), y: Math.max(...ys), z: 0 },
      };
    }
    case "sphere":
      return {
        min: { x: -shape.radius, y: -shape.radius, z: -shape.radius },
        max: { x: shape.radius, y: shape.radius, z: shape.radius },
      };
    case "ellipsoid":
      return {
        min: { x: -shape.size_x / 2, y: -shape.size_y / 2, z: -shape.size_z / 2 },
        max: { x: shape.size_x / 2, y: shape.size_y / 2, z: shape.size_z / 2 },
      };
    case "axes":
      return {
        min: { x: 0, y: 0, z: 0 },
        max: { x: shape.length, y: shape.length, z: shape.length },
      };
  }
}

/** The world-aligned box holding an entity's shape where its transform puts it. */
export function entityBounds(entity: SceneEntity): Bounds {
  const { position, rotation } = entity.transform;
  const turn = new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w);
  const offset = new Vector3(position.x, position.y, position.z);
  const extent = shapeExtent(entity.shape);
  const box = new Box3();
  for (const x of [extent.min.x, extent.max.x]) {
    for (const y of [extent.min.y, extent.max.y]) {
      for (const z of [extent.min.z, extent.max.z]) {
        box.expandByPoint(new Vector3(x, y, z).applyQuaternion(turn).add(offset));
      }
    }
  }
  return { min: point(box.min), max: point(box.max) };
}

/**
 * What is drawn around the selected entity: its bounding box; its origin and
 * own axes, which show its transform; and its label on a leader line. Reads
 * the entity and never changes it.
 */
export function selectionOverlays(
  entity: SceneEntity,
  toggles: OverlayToggles,
): OverlayPrimitive[] {
  const primitives: OverlayPrimitive[] = [];
  const bounds = entityBounds(entity);
  const { position, rotation } = entity.transform;
  const origin: Point3 = { x: position.x, y: position.y, z: position.z };
  if (toggles.box) {
    primitives.push({ id: "box", kind: "box", bounds, color: SELECTION_COLOR });
  }
  if (toggles.axes) {
    const turn = new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w);
    primitives.push({ id: "origin", kind: "point", position: origin, color: SELECTION_COLOR });
    for (const { name, axis, color } of FRAME_AXES) {
      const direction = point(new Vector3(axis.x, axis.y, axis.z).applyQuaternion(turn));
      const length = FRAME_ARROW_LENGTH_M;
      primitives.push({ id: `axis-${name}`, kind: "arrow", origin, direction, length, color });
    }
  }
  if (toggles.label) {
    const top: Point3 = {
      x: (bounds.min.x + bounds.max.x) / 2,
      y: (bounds.min.y + bounds.max.y) / 2,
      z: bounds.max.z,
    };
    const anchor: Point3 = { ...top, z: top.z + LABEL_RISE_M };
    primitives.push({ id: "leader", kind: "line", from: top, to: anchor, color: SELECTION_COLOR });
    const text = entity.label ?? entity.entity_id;
    primitives.push({ id: "label", kind: "label", position: anchor, text });
  }
  return primitives;
}
