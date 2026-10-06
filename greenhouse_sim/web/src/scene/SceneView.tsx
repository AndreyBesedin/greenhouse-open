import { useMemo } from "react";

import { categoryColor } from "../debug/categories";
import { type Colouring, scalarColor, scalarValue } from "../debug/scalar";
import { highlighted } from "../selection";
import type { Color, SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import { InstancedShapes } from "./InstancedShapes";
import { isInstanced, shapeBatches } from "./instancing";
import { placement } from "./placement";
import { RENDERERS } from "./renderers";

/** The colour an entity is drawn in: its category's in the categories' debug
 * view, a colouring's where it has the property, or its own. */
function shownColor(entity: SceneEntity, colouring: Colouring | null, byCategory: boolean): Color {
  const category = byCategory ? categoryColor(entity.kind) : null;
  if (category !== null) {
    return category;
  }
  const value = colouring === null ? null : scalarValue(entity, colouring.property);
  return colouring === null || value === null ? entity.color : scalarColor(value, colouring.range);
}

/**
 * A checked snapshot. Belongs inside the world's z-up group. Cylinders,
 * spheres and ellipsoids, the shapes repeated by the hundred in a greenhouse
 * (posts, rafters, pipes, and plants' stems, leaflets and fruits), are drawn
 * in one instanced batch per kind, per shape and per finish: metal or not.
 * Every other entity, and a highlighted one, which glows, is drawn on its own
 * by its kind's renderer: the selected entity and, if it is part of a plant's
 * organ, the organ's other parts. Either way a click can tell which entity it
 * landed on (`pickEntity`): an entity's own group carries its identifier, and
 * a batch lists its entities.
 */
export function SceneView({
  snapshot,
  selectedId = null,
  colouring = null,
  showBounds = false,
  byCategory = false,
}: {
  snapshot: SceneSnapshot;
  selectedId?: string | null;
  /** Shades the entities that have the property; the others keep their colour. */
  colouring?: Colouring | null;
  /** The greenhouse's bounds are a debug aid: they lie on its walls, and are
   * drawn only when asked for. */
  showBounds?: boolean;
  /** Colours each part of the envelope by its semantic category. */
  byCategory?: boolean;
}) {
  const { batches, single, glowing } = useMemo(() => {
    const glowing = highlighted(snapshot, selectedId);
    return {
      glowing,
      batches: shapeBatches(snapshot.entities).map(({ batch, shape, metallic, entities: all }) => {
        const batched = all.filter((entity) => !glowing.has(entity.entity_id));
        return {
          batch,
          shape,
          metallic,
          entities: batched,
          colors: batched.map((entity) => shownColor(entity, colouring, byCategory)),
          capacity: all.length,
        };
      }),
      single: snapshot.entities.filter(
        (entity) =>
          (!isInstanced(entity) || glowing.has(entity.entity_id)) &&
          (showBounds || entity.kind !== "GREENHOUSE_BOUNDS"),
      ),
    };
  }, [snapshot, selectedId, colouring, showBounds, byCategory]);

  return (
    <>
      {batches.map(({ batch, shape, metallic, entities, colors, capacity }) => (
        <InstancedShapes
          key={`${batch}-${capacity}`}
          shape={shape}
          entities={entities}
          colors={colors}
          capacity={capacity}
          metallic={metallic}
        />
      ))}
      {single.map((entity) => {
        const { position, quaternion } = placement(entity.transform);
        const look = {
          color: shownColor(entity, colouring, byCategory),
          selected: glowing.has(entity.entity_id),
          emphasised: byCategory,
        };
        return (
          <group
            key={entity.entity_id}
            position={position}
            quaternion={quaternion}
            userData={{ entityId: entity.entity_id, entityKind: entity.kind }}
          >
            {RENDERERS[entity.kind](entity, look)}
          </group>
        );
      })}
    </>
  );
}
