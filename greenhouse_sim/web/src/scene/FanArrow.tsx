import { ConeGeometry, CylinderGeometry } from "three";

import { useDisposable } from "../useDisposable";
import type { Color, Cylinder } from "./generated/snapshotTypes";
import { threeColor } from "./ShapeMesh";

// A quarter turn about x lays Three.js's y-aligned cylinder and cone along z.
const ALONG_Z = Math.PI / 2;
// The arrow's parts, in the fan's radii: its shaft's length and thickness,
// and its head's.
const SHAFT_LENGTH = 1.2;
const SHAFT_RADIUS = 0.08;
const HEAD_LENGTH = 0.6;
const HEAD_RADIUS = 0.24;
const SIDES = 16;

/**
 * The way a fan blows: an arrow out of the front of its housing, along its
 * axis, in its colour. In the fan's frame its housing is a cylinder standing
 * on its back face and rising along +z, so the arrow starts at its top.
 */
export function FanArrow({ housing, color }: { housing: Cylinder; color: Color }) {
  const { radius, height } = housing;
  const shaft = useDisposable(
    () =>
      new CylinderGeometry(
        SHAFT_RADIUS * radius,
        SHAFT_RADIUS * radius,
        SHAFT_LENGTH * radius,
        SIDES,
      )
        .rotateX(ALONG_Z)
        .translate(0, 0, height + (SHAFT_LENGTH * radius) / 2),
    [radius, height],
  );
  const head = useDisposable(
    () =>
      new ConeGeometry(HEAD_RADIUS * radius, HEAD_LENGTH * radius, SIDES)
        .rotateX(ALONG_Z)
        .translate(0, 0, height + SHAFT_LENGTH * radius + (HEAD_LENGTH * radius) / 2),
    [radius, height],
  );
  const shown = threeColor(color);
  return (
    <>
      <mesh geometry={shaft}>
        <meshStandardMaterial color={shown} />
      </mesh>
      <mesh geometry={head}>
        <meshStandardMaterial color={shown} />
      </mesh>
    </>
  );
}
