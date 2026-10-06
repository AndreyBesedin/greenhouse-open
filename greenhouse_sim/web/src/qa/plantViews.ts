import type { CameraPose } from "../camera";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";

// The plant lab's first plant at four ages, side by side along +x, a metre
// apart from the origin, as the simulator writes it
// (`tests/test_scene_schema.py --update`).
export const QA_PLANTS_PATH = "/qa/plants";
export const QA_PLANTS_SCENE_URL = "/scenes/qa-plants.json";

// From in front of the row of ages, a little below the tallest one's top,
// far enough back to see the youngest and the oldest, two metres tall, whole.
export const QA_PLANTS_POSE: CameraPose = {
  position: { x: 1.5, y: -3.6, z: 1.2 },
  target: { x: 1.5, y: 0, z: 0.95 },
};

/** The days the time lapse shows, youngest first, from its entities. */
export function timeLapseDays(snapshot: SceneSnapshot): number[] {
  const days = new Set<number>();
  for (const entity of snapshot.entities) {
    const day = entity.properties.day;
    if (typeof day === "number") {
      days.add(day);
    }
  }
  return [...days].sort((a, b) => a - b);
}
