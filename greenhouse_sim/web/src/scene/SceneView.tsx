import { useMemo } from "react";

import { categoryColor } from "../debug/categories";
import { type Colouring, scalarColor, scalarValue } from "../debug/scalar";
import type { Color, SceneEntity, SceneEntityKind, SceneSnapshot } from "./generated/snapshotTypes";
import { InstancedCylinders } from "./InstancedCylinders";
import { placement } from "./placement";
import { RENDERERS } from "./renderers";

// Structural members are metal; plants are not.
const METALLIC_KINDS: ReadonlySet<SceneEntityKind> = new Set(["FRAME"]);

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
 * A checked snapshot. Belongs inside the world's z-up group. Cylinders, the
 * shape repeated by the hundred in a greenhouse (stems, posts, rafters), are
 * drawn in one instanced batch per kind; every other entity, and a selected
 * cylinder, which glows, is drawn on its own by its kind's renderer. Either way
 * a click can tell which entity it landed on (`pickEntity`): an entity's own
 * group carries its identifier, and a batch lists its entities.
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
  const { batches, single } = useMemo(() => {
    const cylinders = new Map<SceneEntityKind, SceneEntity[]>();
    for (const entity of snapshot.entities) {
      if (entity.shape.shape === "cylinder") {
        cylinders.set(entity.kind, [...(cylinders.get(entity.kind) ?? []), entity]);
      }
    }
    return {
      batches: [...cylinders].map(([kind, all]) => {
        const batched = all.filter((entity) => entity.entity_id !== selectedId);
        return {
          kind,
          entities: batched,
          colors: batched.map((entity) => shownColor(entity, colouring, byCategory)),
          capacity: all.length,
        };
      }),
      single: snapshot.entities.filter(
        (entity) =>
          (entity.shape.shape !== "cylinder" || entity.entity_id === selectedId) &&
          (showBounds || entity.kind !== "GREENHOUSE_BOUNDS"),
      ),
    };
  }, [snapshot, selectedId, colouring, showBounds, byCategory]);

  return (
    <>
      {batches.map(({ kind, entities, colors, capacity }) => (
        <InstancedCylinders
          key={`${kind}-${capacity}`}
          entities={entities}
          colors={colors}
          capacity={capacity}
          metallic={METALLIC_KINDS.has(kind)}
        />
      ))}
      {single.map((entity) => {
        const { position, quaternion } = placement(entity.transform);
        const look = {
          color: shownColor(entity, colouring, byCategory),
          selected: entity.entity_id === selectedId,
          emphasised: byCategory,
        };
        return (
          <group
            key={entity.entity_id}
            position={position}
            quaternion={quaternion}
            userData={{ entityId: entity.entity_id }}
          >
            {RENDERERS[entity.kind](entity, look)}
          </group>
        );
      })}
    </>
  );
}
