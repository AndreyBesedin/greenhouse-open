import { Quaternion, Vector3 } from "three";

import { formatMetres } from "../readouts";
import type { SceneEntity, SceneSnapshot, Transform } from "../scene/generated/snapshotTypes";
import type { Point3 } from "../world";
import type { OverlayPrimitive } from "./overlays";

export const DIMENSION_COLOR = "#1f5fbf";
// Each world axis is labelled a little beyond its tip.
const AXIS_LABEL_REACH = 1.1;

/** Where a point given in an entity's own frame lies in the world. */
function inWorld(transform: Transform, point: Point3): Point3 {
  const { position, rotation } = transform;
  const turn = new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w);
  const placed = new Vector3(point.x, point.y, point.z)
    .applyQuaternion(turn)
    .add(new Vector3(position.x, position.y, position.z));
  return { x: placed.x, y: placed.y, z: placed.z };
}

function midpoint(from: Point3, to: Point3): Point3 {
  return { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2, z: (from.z + to.z) / 2 };
}

/**
 * The greenhouse's length, width and height, measured along three edges from
 * its floor corner: x is its length, y its width (decision 0016).
 */
function boundsDimensions(entity: SceneEntity): OverlayPrimitive[] {
  if (entity.shape.shape !== "box") {
    return [];
  }
  const { size_x, size_y, size_z } = entity.shape;
  // The box stands on its frame's origin, so the floor corner is half a size back.
  const corner = { x: -size_x / 2, y: -size_y / 2, z: 0 };
  const edges = [
    { name: "length", size: size_x, end: { ...corner, x: size_x / 2 } },
    { name: "width", size: size_y, end: { ...corner, y: size_y / 2 } },
    { name: "height", size: size_z, end: { ...corner, z: size_z } },
  ];
  const from = inWorld(entity.transform, corner);
  return edges.flatMap(({ name, size, end }) => {
    const to = inWorld(entity.transform, end);
    const id = `${entity.entity_id}-${name}`;
    return [
      { id: `${id}-line`, kind: "line", from, to, color: DIMENSION_COLOR },
      {
        id: `${id}-label`,
        kind: "label",
        position: midpoint(from, to),
        text: `${name} ${formatMetres(size)} m`,
      },
    ] satisfies OverlayPrimitive[];
  });
}

/** The x, y and z of a reference axes marker, just beyond its arrows' tips. */
function axisLabels(entity: SceneEntity): OverlayPrimitive[] {
  if (entity.shape.shape !== "axes") {
    return [];
  }
  const reach = entity.shape.length * AXIS_LABEL_REACH;
  const tips = {
    x: { x: reach, y: 0, z: 0 },
    y: { x: 0, y: reach, z: 0 },
    z: { x: 0, y: 0, z: reach },
  };
  return Object.entries(tips).map(([axis, tip]) => ({
    id: `${entity.entity_id}-${axis}`,
    kind: "label",
    position: inWorld(entity.transform, tip),
    text: axis,
  }));
}

/** Measurements for a scene in debug mode: the greenhouse's dimensions and
 * the names of the world's axes. Reads the scene and never changes it. */
export function sceneDimensionOverlays(snapshot: SceneSnapshot): OverlayPrimitive[] {
  return snapshot.entities.flatMap((entity) => {
    switch (entity.kind) {
      case "GREENHOUSE_BOUNDS":
        return boundsDimensions(entity);
      case "AXES":
        return axisLabels(entity);
      default:
        return [];
    }
  });
}
