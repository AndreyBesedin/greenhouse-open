import { useMemo } from "react";

import { CategoryLegend } from "../debug/CategoryLegend";
import { categoriesIn } from "../debug/categories";
import { Viewport } from "../Viewport";
import { greenhouseExtent } from "./greenhouseViews";
import {
  eaveHeight,
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
 * QA greenhouse, from a fixed view, coloured by category with its legends.
 * The top view cuts the house below its eaves, so that the layout reads from
 * above. Nothing on it changes over time, so it looks the same on every visit.
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
        byCategory
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      />
      <p className="qa-caption" data-testid="qa-caption">
        Layout QA, {view} view
      </p>
      <div className="legends">
        <CategoryLegend categories={categoriesIn(snapshot)} />
      </div>
    </main>
  );
}
