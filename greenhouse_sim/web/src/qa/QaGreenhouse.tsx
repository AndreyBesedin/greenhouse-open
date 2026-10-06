import { useMemo } from "react";

import { CategoryLegend } from "../debug/CategoryLegend";
import { categoriesIn } from "../debug/categories";
import { Viewport } from "../Viewport";
import {
  greenhouseExtent,
  QA_GREENHOUSE_SCENE_URL,
  qaGreenhousePose,
  qaGreenhouseSection,
  qaGreenhouseView,
} from "./greenhouseViews";
import { useSceneFile } from "./useSceneFile";

const ignore = () => undefined;

/**
 * The canonical page for the greenhouse's screenshot tests: the QA greenhouse
 * from one of four fixed views (outside, along an aisle, from the top, and a
 * section with its surfaces coloured by category). Nothing on it changes over
 * time, so it looks the same on every visit.
 */
export function QaGreenhouse({ search }: { search: string }) {
  const view = qaGreenhouseView(search);
  const scene = useSceneFile(QA_GREENHOUSE_SCENE_URL);

  const snapshot = scene.status === "loaded" ? scene.snapshot : null;
  const extent = useMemo(() => (snapshot === null ? null : greenhouseExtent(snapshot)), [snapshot]);
  const pose = useMemo(
    () => (view === null || extent === null ? null : qaGreenhousePose(view, extent)),
    [view, extent],
  );
  const section = useMemo(
    () => (view === null || extent === null ? null : qaGreenhouseSection(view, extent)),
    [view, extent],
  );

  if (view === null) {
    return (
      <p className="qa-caption" role="alert">
        The view must be outside, aisle, top or section.
      </p>
    );
  }
  if (snapshot === null || pose === null) {
    return (
      <p className="qa-caption" data-testid="qa-caption">
        {scene.status === "loading"
          ? "Loading the QA greenhouse…"
          : "The QA greenhouse is missing."}
      </p>
    );
  }
  const byCategory = view === "section";
  return (
    <main className="viewer">
      <Viewport
        snapshot={snapshot}
        presetRequest={null}
        initialPose={pose}
        section={section}
        byCategory={byCategory}
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      />
      <p className="qa-caption" data-testid="qa-caption">
        Greenhouse QA, {view} view
      </p>
      <div className="legends">
        {byCategory && <CategoryLegend categories={categoriesIn(snapshot)} />}
      </div>
    </main>
  );
}
