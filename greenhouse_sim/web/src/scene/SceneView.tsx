import type { SceneSnapshot } from "./generated/snapshotTypes";
import { placement } from "./placement";
import { RENDERERS } from "./renderers";

/** A checked snapshot, drawn entity by entity. Belongs inside the world's z-up group. */
export function SceneView({ snapshot }: { snapshot: SceneSnapshot }) {
  return (
    <>
      {snapshot.entities.map((entity) => {
        const { position, quaternion } = placement(entity.transform);
        return (
          <group key={entity.entity_id} position={position} quaternion={quaternion}>
            {RENDERERS[entity.kind](entity)}
          </group>
        );
      })}
    </>
  );
}
