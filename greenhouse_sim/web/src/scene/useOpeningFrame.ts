import { useEffect, useMemo, useState } from "react";

import { type CameraPose, framing } from "../camera";
import type { Pending } from "../useLoad";
import type { Point3 } from "../world";
import type { SceneSnapshot } from "./generated/snapshotTypes";
import type { SceneState } from "./sceneLoad";

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

/** The box a scene's house stands in: the middle of its floor and its size,
 * in metres, as `framing` frames it; none if the scene bounds no house. */
export function houseBox(snapshot: SceneSnapshot): { base: Point3; size: Point3 } | null {
  const bounds = snapshot.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS");
  return bounds?.shape.shape === "box"
    ? {
        base: bounds.transform.position,
        size: { x: bounds.shape.size_x, y: bounds.shape.size_y, z: bounds.shape.size_z },
      }
    : null;
}

/** The box a scene's house stands in, from the scene the latest request asked
 * for, never one kept on show while another envelope is on its way. */
function useLatestBounds(latestScene: SceneState | Pending) {
  return useMemo(
    () => (latestScene.status === "loaded" ? houseBox(latestScene.snapshot) : null),
    [latestScene],
  );
}

/**
 * Where the camera starts over a scenario opened to look at, with no camera in
 * its address: its house framed, once, rather than from the corner at the
 * world's origin where the presets look. It is not written to the address,
 * which says only what was asked for, and it never moves the camera again: a
 * preset chosen first keeps its place, and so does whatever a person does
 * after it.
 */
export function useOpeningFrame({
  scenarioId,
  latestScene,
  ownCamera,
  presetChosen,
}: {
  scenarioId: string | null;
  latestScene: SceneState | Pending;
  /** Whether the address gives the camera its pose. */
  ownCamera: boolean;
  presetChosen: boolean;
}): CameraPose | null {
  const bounds = useLatestBounds(latestScene);
  const aspect = useWindowAspect();
  const [held, setHeld] = useState<{ scenarioId: string; pose: CameraPose } | null>(null);
  useEffect(() => {
    if (scenarioId === null || bounds === null || ownCamera || presetChosen) {
      return;
    }
    setHeld((was) =>
      was?.scenarioId === scenarioId
        ? was
        : { scenarioId, pose: framing(bounds.base, bounds.size, aspect) },
    );
  }, [scenarioId, bounds, ownCamera, presetChosen, aspect]);
  return held?.scenarioId === scenarioId ? held.pose : null;
}
