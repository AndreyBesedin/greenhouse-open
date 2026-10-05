import { useMemo } from "react";

import { type Colouring, scalarColor, scalarValue } from "../debug/scalar";
import type { Color, SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import { InstancedCylinders } from "./InstancedCylinders";
import { placement } from "./placement";
import { RENDERERS } from "./renderers";

function shownColor(entity: SceneEntity, colouring: Colouring | null): Color {
  const value = colouring === null ? null : scalarValue(entity, colouring.property);
  return colouring === null || value === null ? entity.color : scalarColor(value, colouring.range);
}

/**
 * A checked snapshot. Belongs inside the world's z-up group. Cylinders, the
 * shape repeated by the hundred in a greenhouse, are drawn together in one
 * instanced batch; every other entity, and a selected cylinder, which glows,
 * is drawn on its own by its kind's renderer. Either way a click can tell
 * which entity it landed on (`pickEntity`): an entity's own group carries its
 * identifier, and the batch lists its entities.
 */
export function SceneView({
  snapshot,
  selectedId = null,
  colouring = null,
}: {
  snapshot: SceneSnapshot;
  selectedId?: string | null;
  /** Shades the entities that have the property; the others keep their colour. */
  colouring?: Colouring | null;
}) {
  const { batch, batchColors, capacity, single } = useMemo(() => {
    const cylinders = snapshot.entities.filter((entity) => entity.shape.shape === "cylinder");
    const batched = cylinders.filter((entity) => entity.entity_id !== selectedId);
    return {
      batch: batched,
      batchColors: batched.map((entity) => shownColor(entity, colouring)),
      capacity: cylinders.length,
      single: snapshot.entities.filter(
        (entity) => entity.shape.shape !== "cylinder" || entity.entity_id === selectedId,
      ),
    };
  }, [snapshot, selectedId, colouring]);

  return (
    <>
      {capacity > 0 && (
        <InstancedCylinders
          key={capacity}
          entities={batch}
          colors={batchColors}
          capacity={capacity}
        />
      )}
      {single.map((entity) => {
        const { position, quaternion } = placement(entity.transform);
        const look = {
          color: shownColor(entity, colouring),
          selected: entity.entity_id === selectedId,
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
