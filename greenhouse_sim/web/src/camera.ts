import { MathUtils } from "three";

import type { Point3 } from "./world";

// Camera presets, in world coordinates (metres, z up), all looking at the
// world origin from the same distance. The isometric view is the default, so
// a refresh always returns to it.
export type PresetName = "top" | "front" | "side" | "isometric";

export interface CameraPose {
  position: Point3;
  target: Point3;
}

// The camera's vertical field of view.
export const CAMERA_FIELD_OF_VIEW_DEG = 50;
// The nearest the camera draws, in metres: what lies closer is cut away.
export const CAMERA_NEAR_M = 0.1;
// The nearest the camera comes to the point it orbits, in metres: twice its
// near plane, so that the point and what lies around it stay drawn. A notch of
// the wheel moves the camera a fixed share of its distance to that point, so
// without a floor a long zoom in only ever brings it nearer: inside the near
// plane, where the view stops changing and a notch back out moves the camera
// by a fraction of a millimetre, and at last so near that rounding swallows
// the notches, and the wheel turns back hundreds of them, or for ever, without
// moving it.
export const CAMERA_CLOSEST_M = 0.2;

const VIEW_DISTANCE_M = 9;
// Straight down would leave "up" on screen undefined; leaning a millimetre
// towards -y keeps world +y pointing up the screen in the top view.
const TOP_VIEW_LEAN_M = 0.001;
// Equally far along each of the three axes: the distance divided by √3.
const AXES = 3;
const ISOMETRIC_COMPONENT_M = VIEW_DISTANCE_M / Math.sqrt(AXES);
const ORIGIN: Point3 = { x: 0, y: 0, z: 0 };

export const CAMERA_PRESETS: Record<PresetName, CameraPose> = {
  // Looking down at the ground, x to the right and y up the screen.
  top: { position: { x: 0, y: -TOP_VIEW_LEAN_M, z: VIEW_DISTANCE_M }, target: ORIGIN },
  // From -y, looking along +y: x to the right, z up.
  front: { position: { x: 0, y: -VIEW_DISTANCE_M, z: 0 }, target: ORIGIN },
  // From +x, looking along -x: y to the right, z up.
  side: { position: { x: VIEW_DISTANCE_M, y: 0, z: 0 }, target: ORIGIN },
  // From the front-right-top diagonal, equally far along each axis.
  isometric: {
    position: { x: ISOMETRIC_COMPONENT_M, y: -ISOMETRIC_COMPONENT_M, z: ISOMETRIC_COMPONENT_M },
    target: ORIGIN,
  },
};

// A framed box is aimed at this share of its height up: the floor and what
// stands on it, under the roof.
const FRAMED_AIM_SHARE = 0.3;
// What a framing pose is rounded to, as an address writes it: decimetres.
const FRAMING_DECIMALS = 1;

function toStep(value: number): number {
  return Number(value.toFixed(FRAMING_DECIMALS)) + 0;
}

/**
 * A pose that frames a box standing on the ground, from the default
 * preset's direction: aimed at its middle, some way up its height, and
 * far enough back that all of it is within a view of `aspect`, as a
 * greenhouse is shown whole rather than from its corner at the world's
 * origin, where the presets look.
 */
export function framing(base: Point3, size: Point3, aspect: number): CameraPose {
  const target = { x: base.x, y: base.y, z: base.z + size.z * FRAMED_AIM_SHARE };
  // The farthest corner from the aim, which the view must hold.
  const reach = Math.hypot(size.x / 2, size.y / 2, size.z * (1 - FRAMED_AIM_SHARE));
  // The view's narrower half-angle: its height's, or, in a view taller than
  // wide, its width's.
  const halfHeight = MathUtils.degToRad(CAMERA_FIELD_OF_VIEW_DEG) / 2;
  const half = Math.min(halfHeight, Math.atan(Math.tan(halfHeight) * aspect));
  const distance = reach / Math.sin(half);
  const { position: away } = CAMERA_PRESETS[DEFAULT_PRESET];
  const scale = distance / Math.hypot(away.x, away.y, away.z);
  return {
    position: {
      x: toStep(target.x + away.x * scale),
      y: toStep(target.y + away.y * scale),
      z: toStep(target.z + away.z * scale),
    },
    target: { x: toStep(target.x), y: toStep(target.y), z: toStep(target.z) },
  };
}

export const PRESET_ORDER: readonly PresetName[] = ["top", "front", "side", "isometric"];
export const DEFAULT_PRESET: PresetName = "isometric";

/** A request to move the camera to a preset; `serial` lets the same preset be chosen again. */
export interface PresetRequest {
  preset: PresetName;
  serial: number;
}
