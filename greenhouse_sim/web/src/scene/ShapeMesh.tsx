import { SRGBColorSpace, Color as ThreeColor } from "three";

import type { Color, Shape } from "./generated/snapshotTypes";

// Enough sides for a stem to read as round at greenhouse distances.
const CYLINDER_SIDES = 24;
// A quarter turn about x stands Three.js's y-aligned cylinder up along z.
const STAND_UP: [number, number, number] = [Math.PI / 2, 0, 0];

function threeColor(color: Color): ThreeColor {
  return new ThreeColor().setRGB(color.r, color.g, color.b, SRGBColorSpace);
}

/** A shape drawn in its own frame, as `world/geometry.py` describes it. Inside
 * the world's z-up group, so world sizes and directions apply directly. */
export function ShapeMesh({
  shape,
  color,
  behindLines = false,
}: {
  shape: Shape;
  color: Color;
  /** Drawn just behind lines at the same depth, such as the ground grid. */
  behindLines?: boolean;
}) {
  switch (shape.shape) {
    case "plane":
      return (
        <mesh>
          <planeGeometry args={[shape.size_x, shape.size_y]} />
          <meshStandardMaterial
            color={threeColor(color)}
            polygonOffset={behindLines}
            polygonOffsetFactor={1}
            polygonOffsetUnits={1}
          />
        </mesh>
      );
    case "cylinder":
      // Its base is the frame's origin, so lift it by half its height.
      return (
        <mesh position={[0, 0, shape.height / 2]} rotation={STAND_UP}>
          <cylinderGeometry args={[shape.radius, shape.radius, shape.height, CYLINDER_SIDES]} />
          <meshStandardMaterial color={threeColor(color)} />
        </mesh>
      );
    case "axes":
      return <axesHelper args={[shape.length]} />;
  }
}
