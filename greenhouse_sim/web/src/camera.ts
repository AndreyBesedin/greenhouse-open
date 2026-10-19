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

export const PRESET_ORDER: readonly PresetName[] = ["top", "front", "side", "isometric"];
export const DEFAULT_PRESET: PresetName = "isometric";

/** A request to move the camera to a preset; `serial` lets the same preset be chosen again. */
export interface PresetRequest {
  preset: PresetName;
  serial: number;
}
