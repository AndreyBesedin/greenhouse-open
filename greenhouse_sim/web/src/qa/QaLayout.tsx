import { useMemo } from "react";

import { CategoryLegend } from "../debug/CategoryLegend";
import { categoriesIn } from "../debug/categories";
import { Viewport } from "../Viewport";
import { greenhouseExtent } from "./greenhouseViews";
import {
  eaveHeight,
  isLayoutPlan,
  QA_LAYOUT_SCENE_URL,
  QA_LAYOUT_VIEWS,
  qaLayoutPose,
  qaLayoutSection,
  qaLayoutView,
} from "./layoutViews";
import { useSceneFile } from "./useSceneFile";

const ignore = () => undefined;

/**
 * The canonical page for the layout's QA views: the canonical layout, in the
 * QA greenhouse, from one of three fixed views. The top view is a plan,
 * coloured by category with its legends and cut below the eaves; the view
 * between the rows rides a rail down a path, and the occluded one looks
 * across a row from low down, through the fixtures in its way. Nothing on it
 * changes over time, so it looks the same on every visit.
 */
export function QaLayout({ search }: { search: string }) {
  const view = qaLayoutView(search);
  const scene = useSceneFile(QA_LAYOUT_SCENE_URL);
  const snapshot = scene.status === "loaded" ? scene.snapshot : null;
  const extent = useMemo(() => (snapshot === null ? null : greenhouseExtent(snapshot)), [snapshot]);
  const eaves = useMemo(() => (snapshot === null ? null : eaveHeight(snapshot)), [snapshot]);
  const pose = useMemo(
    () => (view === null || extent === null ? null : qaLayoutPose(view, extent)),
    [view, extent],
  );
  const section = useMemo(
    () => (view === null || eaves === null ? null : qaLayoutSection(view, eaves)),
    [view, eaves],
  );

  if (view === null) {
    return (
      <p className="qa-caption" role="alert">
        The view must be {QA_LAYOUT_VIEWS.join(" or ")}.
      </p>
    );
  }
  if (snapshot === null || pose === null) {
    return (
      <p className="qa-caption" data-testid="qa-caption">
        {scene.status === "loading" ? "Loading the QA layout…" : "The QA layout is missing."}
      </p>
    );
  }
  return (
    <main className="viewer">
      <Viewport
        snapshot={snapshot}
        presetRequest={null}
        initialPose={pose}
        section={section}
        byCategory={isLayoutPlan(view)}
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      />
      <p className="qa-caption" data-testid="qa-caption">
        Layout QA, {view} view
      </p>
      <div className="legends">
        {isLayoutPlan(view) && <CategoryLegend categories={categoriesIn(snapshot)} />}
      </div>
    </main>
  );
}
