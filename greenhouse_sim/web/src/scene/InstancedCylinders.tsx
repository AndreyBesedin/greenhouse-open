import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { CylinderGeometry, type InstancedMesh } from "three";

import type { Color, SceneEntity } from "./generated/snapshotTypes";
import { cylinderMatrices } from "./instancing";
import { CYLINDER_SIDES, STAND_UP, threeColor } from "./ShapeMesh";

/**
 * Many cylinders in one draw call: one mesh, drawn once per entity with that
 * entity's matrix and colour. The mesh lists the entities in drawing order
 * (`userData.entityIds`), so a click on an instance can tell which entity it
 * landed on (`pickEntity`). It holds up to `capacity` cylinders, so the batch
 * can shrink and grow, as a selection leaves and rejoins it, without a new mesh.
 */
export function InstancedCylinders({
  entities,
  colors,
  capacity,
}: {
  entities: readonly SceneEntity[];
  colors: readonly Color[];
  capacity: number;
}) {
  const mesh = useRef<InstancedMesh>(null);
  // A unit cylinder standing on the origin along +z, as `cylinderMatrices` expects.
  const geometry = useMemo(() => {
    const unit = new CylinderGeometry(1, 1, 1, CYLINDER_SIDES);
    return unit.rotateX(STAND_UP[0]).translate(0, 0, 1 / 2);
  }, []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const matrices = useMemo(() => cylinderMatrices(entities), [entities]);

  useLayoutEffect(() => {
    const instanced = mesh.current;
    if (instanced === null) {
      return;
    }
    instanced.instanceMatrix.array.set(matrices);
    instanced.instanceMatrix.needsUpdate = true;
    colors.forEach((color, index) => {
      instanced.setColorAt(index, threeColor(color));
    });
    if (instanced.instanceColor !== null) {
      instanced.instanceColor.needsUpdate = true;
    }
    instanced.count = entities.length;
    instanced.userData.entityIds = entities.map((entity) => entity.entity_id);
    // Bounds for clicks and for culling, around the instances as they now stand.
    instanced.computeBoundingBox();
    instanced.computeBoundingSphere();
  }, [entities, colors, matrices]);

  return (
    <instancedMesh ref={mesh} args={[geometry, undefined, capacity]}>
      <meshStandardMaterial />
    </instancedMesh>
  );
}
