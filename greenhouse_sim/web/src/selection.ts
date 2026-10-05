import type { Object3D } from "three";

import type { SceneEntity, SceneSnapshot } from "./scene/generated/snapshotTypes";

// A click whose pointer moved further than this, in pixels, was a drag that
// orbited the camera, not a pick. React Three Fiber uses the same threshold.
export const CLICK_TOLERANCE_PX = 2;

/** The entity a click landed on: the nearest hit drawn as part of an entity.
 * `SceneView` marks each entity's group with its identifier, and an instanced
 * batch lists its entities in instance order. */
export function pickEntity(
  hits: readonly { object: Object3D; instanceId?: number | undefined }[],
): string | null {
  for (const hit of hits) {
    for (let object: Object3D | null = hit.object; object !== null; object = object.parent) {
      const batch: unknown = object.userData.entityIds;
      if (hit.instanceId !== undefined && Array.isArray(batch)) {
        const instanceOf: unknown = batch[hit.instanceId];
        if (typeof instanceOf === "string") {
          return instanceOf;
        }
      }
      const entityId: unknown = object.userData.entityId;
      if (typeof entityId === "string") {
        return entityId;
      }
    }
  }
  return null;
}

/** The selected entity as the given scene has it. A selection is kept by
 * identifier, so it follows its entity from one live frame to the next. */
export function selectedEntity(
  snapshot: SceneSnapshot | null,
  entityId: string | null,
): SceneEntity | null {
  if (snapshot === null || entityId === null) {
    return null;
  }
  return snapshot.entities.find((entity) => entity.entity_id === entityId) ?? null;
}
