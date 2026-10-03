import type { Transform } from "./generated/snapshotTypes";

/** Where an entity's own frame sits, as Three.js takes it inside the world's
 * z-up group: a position, and a quaternion in Three.js's (x, y, z, w) order. */
export interface Placement {
  position: [number, number, number];
  quaternion: [number, number, number, number];
}

export function placement(transform: Transform): Placement {
  const { position, rotation } = transform;
  return {
    position: [position.x, position.y, position.z],
    quaternion: [rotation.x, rotation.y, rotation.z, rotation.w],
  };
}
