import type { CameraPose } from "../camera";

// The plant lab opens close to its plant, which stands at the world's origin
// about half a metre tall: from the front right, a little above its top.
export const PLANT_LAB_POSE: CameraPose = {
  position: { x: 1.1, y: -1.1, z: 0.8 },
  target: { x: 0, y: 0, z: 0.3 },
};
