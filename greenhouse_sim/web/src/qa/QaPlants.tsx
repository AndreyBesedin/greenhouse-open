import { Viewport } from "../Viewport";
import { QA_PLANTS_POSE, QA_PLANTS_SCENE_URL, timeLapseDays } from "./plantViews";
import { useSceneFile } from "./useSceneFile";

const ignore = () => undefined;

/**
 * The canonical page for the plants' screenshot test: the plant lab's first
 * plant at four ages, side by side, from a fixed view, so that a change to
 * how plants develop or are drawn shows as a change of pixels. Nothing on it
 * changes over time, so it looks the same on every visit.
 */
export function QaPlants() {
  const scene = useSceneFile(QA_PLANTS_SCENE_URL);
  if (scene.status !== "loaded") {
    return (
      <p className="qa-caption" data-testid="qa-caption">
        {scene.status === "loading"
          ? "Loading the plants' time lapse…"
          : "The time lapse is missing."}
      </p>
    );
  }
  const days = timeLapseDays(scene.snapshot);
  return (
    <main className="viewer">
      <Viewport
        snapshot={scene.snapshot}
        presetRequest={null}
        initialPose={QA_PLANTS_POSE}
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      />
      <p className="qa-caption" data-testid="qa-caption">
        Plant QA, days {days.join(", ")}
      </p>
    </main>
  );
}
