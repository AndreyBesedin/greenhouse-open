import type { CameraPose } from "../camera";

// The plant lab opens on its plant, which stands at the world's origin and
// grows from about 20 cm on day 0 to about one and a half metres by its last
// day: from the front right, far enough to see it whole on that day.
export const PLANT_LAB_POSE: CameraPose = {
  position: { x: 2.0, y: -2.0, z: 1.2 },
  target: { x: 0, y: 0, z: 0.75 },
};

// The plant lab's run, from its transplant on day 0 to this day, as the
// simulator's lab runs it (`services/plants.py`).
export const PLANT_LAB_LAST_DAY = 60;
