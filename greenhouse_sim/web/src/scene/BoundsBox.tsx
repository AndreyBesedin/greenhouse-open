import { useEffect, useMemo } from "react";
import { BoxGeometry, EdgesGeometry } from "three";

import { SELECTION_COLOR } from "../debug/overlays";
import type { Box, Color } from "./generated/snapshotTypes";
import { threeColor } from "./ShapeMesh";

// See-through enough to show everything inside the bounds.
const BOUNDS_OPACITY = 0.12;

// Faces that clicks pass through, so the bounds never hide what they enclose
// from a pick; their edges can still be clicked.
function passThrough(): void {}

/**
 * A space's bounds: a translucent box with drawn edges. Its base is centred on
 * its frame's origin, as `world/geometry.py` stands a box. Selected, its edges
 * take the selection colour.
 */
export function BoundsBox({
  shape,
  color,
  highlighted,
}: {
  shape: Box;
  color: Color;
  highlighted: boolean;
}) {
  const box = useMemo(
    () => new BoxGeometry(shape.size_x, shape.size_y, shape.size_z),
    [shape.size_x, shape.size_y, shape.size_z],
  );
  const edges = useMemo(() => new EdgesGeometry(box), [box]);
  useEffect(
    () => () => {
      box.dispose();
      edges.dispose();
    },
    [box, edges],
  );
  const fill = threeColor(color);

  return (
    <group position={[0, 0, shape.size_z / 2]}>
      <mesh geometry={box} raycast={passThrough}>
        <meshStandardMaterial
          color={fill}
          transparent
          opacity={BOUNDS_OPACITY}
          depthWrite={false}
        />
      </mesh>
      <lineSegments geometry={edges}>
        <lineBasicMaterial color={highlighted ? SELECTION_COLOR : fill} />
      </lineSegments>
    </group>
  );
}
