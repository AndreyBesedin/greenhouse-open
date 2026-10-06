import type { CameraPose } from "../camera";
import type { SectionPlane } from "../Section";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Extent } from "./greenhouseViews";

// The canonical layout the layout's views draw, in the QA greenhouse, as the
// simulator writes it (`tests/test_scene_schema.py --update`).
export const QA_LAYOUT_PATH = "/qa/layout";
export const QA_LAYOUT_SCENE_URL = "/scenes/qa-layout.json";
export const QA_LAYOUT_VIEWS = ["top", "between-rows", "occluded"] as const;
export type QaLayoutView = (typeof QA_LAYOUT_VIEWS)[number];

// The canonical layout's rows run along the house at y = 2.0 m and every
// 1.6 m on, so its paths between them run at y = 2.8 m, 4.4 m, and so on,
// each with a pipe rail along its middle.
const FIRST_PATH_Y_M = 2.8;
const SECOND_PATH_Y_M = 4.4;
// A camera on a trolley riding the second path's rail, a metre up, just past
// the front aisle, looking down the path to the back of the house.
const TROLLEY_START_X_M = 1.6;
const TROLLEY_CAMERA_HEIGHT_M = 1.0;
const AT_THE_BACK_M = 2;
// A camera low in the first path, between its rail's tubes, looking across
// the second row: rail tubes, legs and a gutter stand in its way.
const LOW_CAMERA = { x: 4.0, z: 0.35 };
const LOW_TARGET = { x: 6.5, y: SECOND_PATH_Y_M, z: 0.6 };

const TOP_RISE_M = 22;
// Straight down would leave "up" undefined; the top view leans a millimetre.
const TOP_LEAN_M = 0.001;
// The top view cuts the house this far below its eaves, so that the roof and
// its gutters do not hide the layout.
const BELOW_THE_EAVES_M = 0.05;

/** The views coloured by category and cut below the eaves, so that the
 * layout reads from above; the others look as a camera would see them. */
export function isLayoutPlan(view: QaLayoutView): boolean {
  return view === "top";
}

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
    case "between-rows":
      return {
        position: { x: TROLLEY_START_X_M, y: SECOND_PATH_Y_M, z: TROLLEY_CAMERA_HEIGHT_M },
        target: { x: length - AT_THE_BACK_M, y: SECOND_PATH_Y_M, z: TROLLEY_CAMERA_HEIGHT_M },
      };
    case "occluded":
      return {
        position: { x: LOW_CAMERA.x, y: FIRST_PATH_Y_M, z: LOW_CAMERA.z },
        target: LOW_TARGET,
      };
  }
}

/** The top view keeps what lies below the eaves; the others are not cut. */
export function qaLayoutSection(view: QaLayoutView, eaves: number): SectionPlane | null {
  return isLayoutPlan(view)
    ? { normal: { x: 0, y: 0, z: -1 }, distance: eaves - BELOW_THE_EAVES_M }
    : null;
}
