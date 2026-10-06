import type { OverlayPrimitive } from "../debug/overlays";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Point3 } from "../world";

// A plant's name floats this far above its highest organ, on a leader line.
const NAME_RISE_M = 0.2;
const NAME_COLOR = "#3d3d3d";

/** Each plant's name above it: from where its stem stands to above its
 * highest organ, over its base. */
export function plantNameOverlays(snapshot: SceneSnapshot): OverlayPrimitive[] {
  const plants = new Map<string, { base: Point3 | null; top: number }>();
  for (const entity of snapshot.entities) {
    const plantId = entity.properties.plant_id;
    if (typeof plantId !== "string") {
      continue;
    }
    const plant = plants.get(plantId) ?? { base: null, top: 0 };
    const { x, y, z } = entity.transform.position;
    plant.top = Math.max(plant.top, z);
    if (entity.entity_id === `${plantId}_n01_internode`) {
      plant.base = { x, y, z };
    }
    plants.set(plantId, plant);
  }
  return [...plants.entries()].flatMap(([plantId, { base, top }]) => {
    if (base === null) {
      return [];
    }
    const above = { ...base, z: top };
    const anchor = { ...base, z: top + NAME_RISE_M };
    return [
      { id: `${plantId}-leader`, kind: "line", from: above, to: anchor, color: NAME_COLOR },
      { id: `${plantId}-name`, kind: "label", position: anchor, text: plantId },
    ] satisfies OverlayPrimitive[];
  });
}
