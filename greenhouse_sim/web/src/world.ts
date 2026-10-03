// The simulator's world is right-handed with z up, in metres (decision 0007).
// Three.js is y up. The viewer converts once, at the root of its scene: world
// content is drawn inside a group rotated by this, and nowhere else.
//
// A rotation of -90° about x maps world (x, y, z) to Three.js (x, z, -y), so
// world +z points up the screen and handedness is kept.
export const WORLD_TO_VIEWER_ROTATION: [number, number, number] = [-Math.PI / 2, 0, 0];

export interface Point3 {
  x: number;
  y: number;
  z: number;
}

/** Where a world point appears in Three.js's own axes. */
export function worldToViewer(point: Point3): Point3 {
  return { x: point.x, y: point.z, z: -point.y };
}

/** Where a point drawn in Three.js's axes lies in the world: the inverse of `worldToViewer`. */
export function viewerToWorld(point: Point3): Point3 {
  return { x: point.x, y: -point.z, z: point.y };
}
