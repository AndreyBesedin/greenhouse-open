import type { Object3D } from "three";

import type { SceneEntity, SceneSnapshot } from "./scene/generated/snapshotTypes";

// A click whose pointer moved further than this, in pixels, was a drag that
// orbited the camera, not a pick. React Three Fiber uses the same threshold.
export const CLICK_TOLERANCE_PX = 2;

type Hit = { object: Object3D; instanceId?: number | undefined };

// What everything else stands on: picked only when nothing but glazing lies
// along the click.
const BACKGROUND_KINDS: ReadonlySet<string> = new Set(["FLOOR", "GROUND"]);
// See-through volumes kept for a purpose: picked before the floor they stand
// on, but after anything solid inside them.
const VOLUME_KINDS: ReadonlySet<string> = new Set(["SERVICE_ZONE", "KEEP_OUT"]);

/**
 * The entity a click landed on: the nearest hit drawn as part of an entity.
 * `SceneView` marks each entity's group with its identifier and kind, and an
 * instanced batch lists its entities in instance order. Hits rank by what
 * they are: anything solid first; then the see-through volumes of zones; then
 * the floor; and glazing, which is see-through, last. A click through a
 * greenhouse's glass reaches the plants and floor inside, and a click on the
 * floor inside a zone picks the zone.
 */
export function pickEntity(hits: readonly Hit[]): string | null {
  const ranks: ((hit: Hit) => boolean)[] = [
    (hit) => !isSeeThrough(hit) && !BACKGROUND_KINDS.has(kindOf(hit)),
    (hit) => isSeeThrough(hit) && VOLUME_KINDS.has(kindOf(hit)),
    (hit) => !isSeeThrough(hit),
  ];
  for (const rank of ranks) {
    const picked = nearestEntity(hits.filter(rank));
    if (picked !== null) {
      return picked;
    }
  }
  return nearestEntity(hits);
}

function isSeeThrough(hit: Hit): boolean {
  return hit.object.userData.seeThrough === true;
}

/** The kind of the entity a hit was drawn for, or "" for a batch or nothing. */
function kindOf(hit: Hit): string {
  for (let object: Object3D | null = hit.object; object !== null; object = object.parent) {
    const kind: unknown = object.userData.entityKind;
    if (typeof kind === "string") {
      return kind;
    }
  }
  return "";
}

function nearestEntity(hits: readonly Hit[]): string | null {
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

/** The organ an entity draws a part of, if it draws one: a plant's organs
 * may each be drawn with several entities, such as a leaf's petiole, rachis
 * and leaflets. */
export function organOf(entity: SceneEntity): string | null {
  const organ = entity.properties.organ_id;
  return typeof organ === "string" ? organ : null;
}

/** The plant an entity draws part of, if it draws one. */
export function plantOf(entity: SceneEntity | null): string | null {
  const plant = entity?.properties.plant_id;
  return typeof plant === "string" ? plant : null;
}

/** The entity that stands for an organ when it is chosen by name: the first
 * part of it the scene draws. */
export function entityOfOrgan(snapshot: SceneSnapshot | null, organId: string): string | null {
  const entity = snapshot?.entities.find((candidate) => organOf(candidate) === organId);
  return entity?.entity_id ?? null;
}

/** What a selection highlights: the selected entity and, if it draws part of
 * an organ, every other part of that organ. */
export function highlighted(
  snapshot: SceneSnapshot | null,
  entityId: string | null,
): ReadonlySet<string> {
  const entity = selectedEntity(snapshot, entityId);
  if (snapshot === null || entity === null) {
    return new Set();
  }
  const organ = organOf(entity);
  if (organ === null) {
    return new Set([entity.entity_id]);
  }
  return new Set(
    snapshot.entities
      .filter((candidate) => organOf(candidate) === organ)
      .map((candidate) => candidate.entity_id),
  );
}
