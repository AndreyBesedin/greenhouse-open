import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { ConeGeometry, CylinderGeometry, type InstancedMesh } from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import { threeColor } from "../scene/ShapeMesh";
import { fieldArrows, MATRIX_SIZE } from "./arrows";
import type { EnvironmentField } from "./field";

// The unit arrow, standing on its origin along +z, one long: a shaft for this
// share of its length, and a head twice as wide for the rest.
const SHAFT_SHARE = 0.65;
const HEAD_WIDTH = 2;
const ROUND_SIDES = 8;
// A quarter turn about x stands Three.js's y-aligned shapes up along z.
const STAND_UP = Math.PI / 2;

function unitArrow() {
  const shaft = new CylinderGeometry(1 / 2, 1 / 2, SHAFT_SHARE, ROUND_SIDES)
    .rotateX(STAND_UP)
    .translate(0, 0, SHAFT_SHARE / 2);
  const head = new ConeGeometry(HEAD_WIDTH / 2, 1 - SHAFT_SHARE, ROUND_SIDES)
    .rotateX(STAND_UP)
    .translate(0, 0, SHAFT_SHARE + (1 - SHAFT_SHARE) / 2);
  const arrow = mergeGeometries([shaft, head]);
  shaft.dispose();
  head.dispose();
  return arrow;
}

/** A field's air velocity as arrows, one at every cell, in one draw call. */
export function FieldArrows({ field }: { field: EnvironmentField }) {
  const mesh = useRef<InstancedMesh>(null);
  const geometry = useMemo(unitArrow, []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const velocity = field.channels.velocity;
  const arrows = useMemo(
    () => (velocity === undefined ? null : fieldArrows(field, velocity)),
    [field, velocity],
  );
  const count = arrows === null ? 0 : arrows.matrices.length / MATRIX_SIZE;

  useLayoutEffect(() => {
    const instanced = mesh.current;
    if (instanced === null || arrows === null) {
      return;
    }
    instanced.instanceMatrix.array.set(arrows.matrices);
    instanced.instanceMatrix.needsUpdate = true;
    arrows.colors.forEach((color, index) => {
      instanced.setColorAt(index, threeColor(color));
    });
    if (instanced.instanceColor !== null) {
      instanced.instanceColor.needsUpdate = true;
    }
    instanced.computeBoundingSphere();
  }, [arrows]);

  if (count === 0) {
    return null;
  }
  return (
    <instancedMesh key={count} ref={mesh} args={[geometry, undefined, count]} raycast={() => null}>
      <meshStandardMaterial />
    </instancedMesh>
  );
}
