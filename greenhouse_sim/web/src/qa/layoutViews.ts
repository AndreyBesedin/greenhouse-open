import type { CameraPose } from "../camera";
import type { SectionPlane } from "../Section";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Extent } from "./greenhouseViews";

// The canonical layout the layout's views draw, in the QA greenhouse, as the
// simulator writes it (`tests/test_scene_schema.py --update`).
export const QA_LAYOUT_PATH = "/qa/layout";
export const QA_LAYOUT_SCENE_URL = "/scenes/qa-layout.json";
export const QA_LAYOUT_VIEWS = ["top"] as const;
export type QaLayoutView = (typeof QA_LAYOUT_VIEWS)[number];

const TOP_RISE_M = 22;
// Straight down would leave "up" undefined; the top view leans a millimetre.
const TOP_LEAN_M = 0.001;
// The top view cuts the house this far below its eaves, so that the roof and
// its gutters do not hide the layout.
const BELOW_THE_EAVES_M = 0.05;

/** The view a QA address asks for, or the top view by default; null for a
 * view there is not. */
export function qaLayoutView(search: string): QaLayoutView | null {
  const view = new URLSearchParams(search).get("view") ?? "top";
  return (QA_LAYOUT_VIEWS as readonly string[]).includes(view) ? (view as QaLayoutView) : null;
}

/** How high the greenhouse's eaves stand: where the tops of its gutters are. */
export function eaveHeight(snapshot: SceneSnapshot): number | null {
  const tops = snapshot.entities.flatMap((entity) =>
    entity.kind === "GUTTER" && entity.shape.shape === "box"
      ? [entity.transform.position.z + entity.shape.size_z]
      : [],
  );
  return tops.length === 0 ? null : Math.max(...tops);
}

/** Where each view's camera stands and looks, for a greenhouse of `extent`. */
export function qaLayoutPose(view: QaLayoutView, extent: Extent): CameraPose {
  const { length, width } = extent;
  switch (view) {
    case "top":
      return {
        position: { x: length / 2, y: width / 2 - TOP_LEAN_M, z: TOP_RISE_M },
        target: { x: length / 2, y: width / 2, z: 0 },
      };
  }
}

/** The top view keeps what lies below the eaves. */
export function qaLayoutSection(view: QaLayoutView, eaves: number): SectionPlane | null {
  switch (view) {
    case "top":
      return { normal: { x: 0, y: 0, z: -1 }, distance: eaves - BELOW_THE_EAVES_M };
  }
}
