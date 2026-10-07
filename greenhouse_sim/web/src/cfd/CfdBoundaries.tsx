import { useEffect, useMemo } from "react";
import { BufferAttribute, BufferGeometry, DoubleSide } from "three";

import {
  type BoundaryShape,
  boundaryOutlines,
  boundaryShape,
  CFD_COLORS,
  FACE_CATEGORIES,
} from "./boundaries";
import type { CfdGeometry } from "./generated/geometryTypes";

const XYZ = 3;
// The domain's faces are lightly tinted, so that the scene shows through
// them, and its openings and obstacles, what the view is for, strongly.
const FACE_OPACITY = 0.15;
const FEATURE_OPACITY = 0.7;
// A quarter turn, which turns Three.js's own planes, square to z, to be
// square to x or y.
const QUARTER_TURN = Math.PI / 2;
const PLANE_TURNS = {
  x: [0, QUARTER_TURN, 0],
  y: [QUARTER_TURN, 0, 0],
  z: [0, 0, 0],
} as const;

function Fill({ shape }: { shape: BoundaryShape }) {
  const { centre, size, normal } = shape;
  const material = (
    <meshBasicMaterial
      color={CFD_COLORS[shape.category]}
      side={DoubleSide}
      transparent
      opacity={FACE_CATEGORIES.has(shape.category) ? FACE_OPACITY : FEATURE_OPACITY}
      depthWrite={false}
    />
  );
  const position: [number, number, number] = [centre.x, centre.y, centre.z];
  if (normal === null) {
    return (
      <mesh position={position} raycast={() => null}>
        <boxGeometry args={[size.x, size.y, size.z]} />
        {material}
      </mesh>
    );
  }
  // A plane's width and height, along its own x and y once turned.
  const across = { x: [size.z, size.y], y: [size.x, size.z], z: [size.x, size.y] }[normal];
  return (
    <mesh position={position} rotation={[...PLANE_TURNS[normal]]} raycast={() => null}>
      <planeGeometry args={[across[0], across[1]]} />
      {material}
    </mesh>
  );
}

/** The boundaries of a CFD domain as the solver is given them, each filled
 * and outlined in its category's colour. Clicks pass through. */
export function CfdBoundaries({ geometry }: { geometry: CfdGeometry }) {
  const shapes = useMemo(() => geometry.boundaries.map(boundaryShape), [geometry]);
  const outlines = useMemo(() => {
    const { positions, colors } = boundaryOutlines(shapes);
    const lines = new BufferGeometry();
    lines.setAttribute("position", new BufferAttribute(positions, XYZ));
    lines.setAttribute("color", new BufferAttribute(colors, XYZ));
    return lines;
  }, [shapes]);
  useEffect(() => () => outlines.dispose(), [outlines]);
  return (
    <group name="cfd-boundaries">
      {shapes.map((shape) => (
        <Fill key={shape.name} shape={shape} />
      ))}
      <lineSegments geometry={outlines} raycast={() => null}>
        <lineBasicMaterial vertexColors />
      </lineSegments>
    </group>
  );
}
