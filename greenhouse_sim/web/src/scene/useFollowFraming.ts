import { useEffect, useMemo, useState } from "react";

import { type CameraPose, framing } from "../camera";
import type { Pending } from "../useLoad";
import type { Point3 } from "../world";
import type { SceneState } from "./sceneLoad";
import type { SetSource } from "./useSource";

// How near the camera may stand to the pose framed for it, in metres, and
// still be taken as not moved since: the HUD samples it as drawn.
const FRAMED_STILL_M = 0.01;

function samePoint(a: Point3, b: Point3): boolean {
  return a.x === b.x && a.y === b.y && a.z === b.z;
}

function samePose(a: CameraPose, b: CameraPose): boolean {
  return samePoint(a.position, b.position) && samePoint(a.target, b.target);
}

/** The window's width over its height, as it changes. */
function useWindowAspect(): number {
  const [aspect, setAspect] = useState(() => window.innerWidth / window.innerHeight);
  useEffect(() => {
    const resized = () => setAspect(window.innerWidth / window.innerHeight);
    window.addEventListener("resize", resized);
    return () => window.removeEventListener("resize", resized);
  }, []);
  return aspect;
}

/**
 * A run followed without a camera of its own is shown whole, its house
 * framed, rather than from its corner at the world's origin, where the
 * presets look; the address keeps the pose (`camera`). Framed from the scene
 * the latest request asked for (`latestScene`), never one kept on show while
 * another envelope is on its way; framed again as the window changes shape,
 * as when it is moved beside a consumer's, while the camera stands where it
 * was framed (`cameraAt`, as the HUD samples it), never once a person has
 * moved it.
 */
export function useFollowFraming({
  followed,
  latestScene,
  camera,
  cameraAt,
  setSource,
}: {
  followed: string | null;
  latestScene: SceneState | Pending;
  camera: CameraPose | undefined;
  cameraAt: Point3 | null;
  setSource: (change: SetSource) => void;
}): void {
  const latestBounds = useMemo(() => {
    const bounds =
      latestScene.status === "loaded"
        ? latestScene.snapshot.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS")
        : undefined;
    return bounds?.shape.shape === "box"
      ? {
          base: bounds.transform.position,
          size: { x: bounds.shape.size_x, y: bounds.shape.size_y, z: bounds.shape.size_z },
        }
      : null;
  }, [latestScene]);
  const aspect = useWindowAspect();
  // The pose last framed here, to tell it from one a person chose.
  const [framed, setFramed] = useState<CameraPose | null>(null);
  useEffect(() => {
    if (followed === null || latestBounds === null) {
      return;
    }
    const untouched =
      camera === undefined ||
      (framed !== null &&
        samePose(camera, framed) &&
        cameraAt !== null &&
        Math.hypot(
          cameraAt.x - framed.position.x,
          cameraAt.y - framed.position.y,
          cameraAt.z - framed.position.z,
        ) < FRAMED_STILL_M);
    if (!untouched) {
      return;
    }
    const pose = framing(latestBounds.base, latestBounds.size, aspect);
    if (camera !== undefined && samePose(camera, pose)) {
      return;
    }
    setFramed(pose);
    setSource((current) =>
      current.kind === "scenario" && current.follow ? { ...current, camera: pose } : current,
    );
  }, [followed, latestBounds, aspect, camera, framed, cameraAt, setSource]);
}
