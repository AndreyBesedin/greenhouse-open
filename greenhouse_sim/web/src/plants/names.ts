import type { OverlayPrimitive } from "../debug/overlays";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Point3 } from "../world";

// A plant's name floats this far above its highest organ, on a leader line.
const NAME_RISE_M = 0.2;
const NAME_COLOR = "#3d3d3d";

/** Each plant's name above it: from where its stem stands to above its
 * highest organ, over its base; a plant drawn whole, as the simple daily
 * model's are, from its top. `more` gives a plant's label more after its
 * name, such as its light in QA mode (P09.6). */
export function plantNameOverlays(
  snapshot: SceneSnapshot,
  more: (plantId: string) => string | null = () => null,
): OverlayPrimitive[] {
  const plants = new Map<string, { base: Point3 | null; top: number }>();
  for (const entity of snapshot.entities) {
    const { x, y, z } = entity.transform.position;
    if (entity.kind === "PLANT") {
      // A stem standing on its frame's origin.
      const height = entity.shape.shape === "cylinder" ? entity.shape.height : 0;
      plants.set(entity.entity_id, { base: { x, y, z }, top: z + height });
      continue;
    }
    const plantId = entity.properties.plant_id;
    if (typeof plantId !== "string") {
      continue;
    }
    const plant = plants.get(plantId) ?? { base: null, top: 0 };
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
    const after = more(plantId);
    return [
      { id: `${plantId}-leader`, kind: "line", from: above, to: anchor, color: NAME_COLOR },
      {
        id: `${plantId}-name`,
        kind: "label",
        position: anchor,
        text: after === null ? plantId : `${plantId} ${after}`,
      },
    ] satisfies OverlayPrimitive[];
  });
}
