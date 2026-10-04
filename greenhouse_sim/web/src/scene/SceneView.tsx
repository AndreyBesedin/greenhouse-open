import { type Colouring, scalarColor, scalarValue } from "../debug/scalar";
import type { Color, SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import { placement } from "./placement";
import { RENDERERS } from "./renderers";

function shownColor(entity: SceneEntity, colouring: Colouring | null): Color {
  const value = colouring === null ? null : scalarValue(entity, colouring.property);
  return colouring === null || value === null ? entity.color : scalarColor(value, colouring.range);
}

/**
 * A checked snapshot, drawn entity by entity. Belongs inside the world's z-up
 * group. Each entity's group carries its identifier, so a click can tell which
 * entity it landed on (`pickEntity`).
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
  return (
    <>
      {snapshot.entities.map((entity) => {
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
