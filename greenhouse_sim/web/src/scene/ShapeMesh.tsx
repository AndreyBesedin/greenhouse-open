import { useEffect, useMemo } from "react";
import {
  BoxGeometry,
  type BufferGeometry,
  DoubleSide,
  FrontSide,
  PlaneGeometry,
  ShapeGeometry,
  SRGBColorSpace,
  Color as ThreeColor,
  Shape as ThreeShape,
  Vector2,
} from "three";

import { SELECTION_COLOR } from "../debug/overlays";
import type { Box, Color, Plane, Polygon, Shape } from "./generated/snapshotTypes";

// Enough sides for a stem to read as round at greenhouse distances.
export const CYLINDER_SIDES = 24;
// A quarter turn about x stands Three.js's y-aligned cylinder up along z.
export const STAND_UP: [number, number, number] = [Math.PI / 2, 0, 0];
// A selected shape glows in the selection colour, enough to stand out in
// daylight without hiding its own colour.
const HIGHLIGHT_INTENSITY = 0.6;
const NO_GLOW = "#000000";

/** A box, plane or polygon as Three.js geometry, in the shape's own frame:
 * a box centred on its middle (lift it onto its base), a plane centred on the
 * origin, a polygon at its corners, both facing +z. */
export function flatGeometry(shape: Box | Plane | Polygon): BufferGeometry {
  switch (shape.shape) {
    case "box":
      return new BoxGeometry(shape.size_x, shape.size_y, shape.size_z);
    case "plane":
      return new PlaneGeometry(shape.size_x, shape.size_y);
    case "polygon":
      return new ShapeGeometry(
        new ThreeShape(shape.points.map((point) => new Vector2(point.x, point.y))),
      );
  }
}

/** A flat polygon, drawn from both sides. */
function PolygonMesh({ shape, color, glow }: { shape: Polygon; color: Color; glow: object }) {
  const geometry = useMemo(() => flatGeometry(shape), [shape]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color={threeColor(color)} side={DoubleSide} {...glow} />
    </mesh>
  );
}

export function threeColor(color: Color): ThreeColor {
  return new ThreeColor().setRGB(color.r, color.g, color.b, SRGBColorSpace);
}

/** A shape drawn in its own frame, as `world/geometry.py` describes it. Inside
 * the world's z-up group, so world sizes and directions apply directly. */
export function ShapeMesh({
  shape,
  color,
  highlighted = false,
  behindLines = false,
  doubleSided = false,
}: {
  shape: Shape;
  color: Color;
  highlighted?: boolean;
  /** Drawn from behind as well, such as a panel seen from either side. */
  doubleSided?: boolean;
  /** Drawn just behind lines at the same depth, such as the ground grid. */
  behindLines?: boolean;
}) {
  const glow = {
    emissive: highlighted ? SELECTION_COLOR : NO_GLOW,
    emissiveIntensity: highlighted ? HIGHLIGHT_INTENSITY : 0,
  };
  switch (shape.shape) {
    case "plane":
      return (
        <mesh>
          <planeGeometry args={[shape.size_x, shape.size_y]} />
          <meshStandardMaterial
            color={threeColor(color)}
            {...glow}
            side={doubleSided ? DoubleSide : FrontSide}
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
          <meshStandardMaterial color={threeColor(color)} {...glow} />
        </mesh>
      );
    case "box":
      // Its base is the frame's origin, so lift it by half its height.
      return (
        <mesh position={[0, 0, shape.size_z / 2]}>
          <boxGeometry args={[shape.size_x, shape.size_y, shape.size_z]} />
          <meshStandardMaterial color={threeColor(color)} {...glow} />
        </mesh>
      );
    case "polygon":
      return <PolygonMesh shape={shape} color={color} glow={glow} />;
    case "axes":
      // Lines cannot glow; the selection's bounding box marks it instead.
      return <axesHelper args={[shape.length]} />;
  }
}
