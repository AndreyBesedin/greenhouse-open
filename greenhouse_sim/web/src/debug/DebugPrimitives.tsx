import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { ArrowHelper, Box3, Box3Helper, Vector3 } from "three";

import { type Point3, worldToViewer } from "../world";
import type { Bounds, OverlayPrimitive } from "./overlays";

// A debug point keeps the same size on screen at any distance.
const POINT_SIZE_PX = 8;
// An arrow's head, as shares of its length and of its head's length.
const ARROW_HEAD_LENGTH_SHARE = 0.25;
const ARROW_HEAD_WIDTH_SHARE = 0.5;
const COMPONENTS_PER_POINT = 3;

function vector(point: Point3): Vector3 {
  return new Vector3(point.x, point.y, point.z);
}

function positions(...points: Point3[]): Float32Array {
  return new Float32Array(points.flatMap((point) => [point.x, point.y, point.z]));
}

export function DebugPoint({ position, color }: { position: Point3; color: string }) {
  const array = useMemo(() => positions(position), [position]);
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[array, COMPONENTS_PER_POINT]} />
      </bufferGeometry>
      <pointsMaterial color={color} size={POINT_SIZE_PX} sizeAttenuation={false} />
    </points>
  );
}

export function DebugArrow({
  origin,
  direction,
  length,
  color,
}: {
  origin: Point3;
  direction: Point3;
  length: number;
  color: string;
}) {
  const arrow = useMemo(() => {
    const headLength = length * ARROW_HEAD_LENGTH_SHARE;
    return new ArrowHelper(
      vector(direction).normalize(),
      vector(origin),
      length,
      color,
      headLength,
      headLength * ARROW_HEAD_WIDTH_SHARE,
    );
  }, [origin, direction, length, color]);
  useEffect(() => () => arrow.dispose(), [arrow]);
  return <primitive object={arrow} />;
}

export function DebugBox({ bounds, color }: { bounds: Bounds; color: string }) {
  const box = useMemo(
    () => new Box3Helper(new Box3(vector(bounds.min), vector(bounds.max)), color),
    [bounds, color],
  );
  useEffect(() => () => box.dispose(), [box]);
  return <primitive object={box} />;
}

export function DebugLine({ from, to, color }: { from: Point3; to: Point3; color: string }) {
  const array = useMemo(() => positions(from, to), [from, to]);
  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[array, COMPONENTS_PER_POINT]} />
      </bufferGeometry>
      <lineBasicMaterial color={color} />
    </lineSegments>
  );
}

/** Text that stays upright and the same size on screen, over the view at a
 * world point. It is a page element, so it reads crisply and can be found by
 * its text. */
export function DebugLabel({ position, text }: { position: Point3; text: string }) {
  const container = useThree((state) => state.gl.domElement.parentElement);
  const element = useMemo(() => document.createElement("div"), []);
  const projected = useMemo(() => new Vector3(), []);

  useEffect(() => {
    element.className = "debug-label";
    element.dataset.testid = "debug-label";
    container?.appendChild(element);
    return () => element.remove();
  }, [container, element]);

  useEffect(() => {
    element.textContent = text;
  }, [element, text]);

  useFrame(({ camera, size }) => {
    const viewer = worldToViewer(position);
    projected.set(viewer.x, viewer.y, viewer.z).project(camera);
    // Beyond the far plane, or behind the camera, which projection also puts there.
    element.hidden = projected.z > 1;
    const x = ((projected.x + 1) / 2) * size.width;
    const y = ((1 - projected.y) / 2) * size.height;
    element.style.transform = `translate(${x}px, ${y}px) translate(-50%, -100%)`;
  });

  return null;
}

function OverlayPrimitiveView({ primitive }: { primitive: OverlayPrimitive }) {
  switch (primitive.kind) {
    case "point":
      return <DebugPoint position={primitive.position} color={primitive.color} />;
    case "arrow":
      return (
        <DebugArrow
          origin={primitive.origin}
          direction={primitive.direction}
          length={primitive.length}
          color={primitive.color}
        />
      );
    case "box":
      return <DebugBox bounds={primitive.bounds} color={primitive.color} />;
    case "line":
      return <DebugLine from={primitive.from} to={primitive.to} color={primitive.color} />;
    case "label":
      return <DebugLabel position={primitive.position} text={primitive.text} />;
  }
}

/** Draws debug primitives. Belongs inside the world's z-up group, outside
 * anything that can be clicked, so that overlays never get in a pick's way. */
export function Overlays({ primitives }: { primitives: readonly OverlayPrimitive[] }) {
  return (
    <>
      {primitives.map((primitive) => (
        <OverlayPrimitiveView key={primitive.id} primitive={primitive} />
      ))}
    </>
  );
}
