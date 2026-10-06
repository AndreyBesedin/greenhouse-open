import type { CameraPose } from "../camera";
import type { SectionPlane } from "../Section";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";

// The canonical greenhouse the screenshot tests draw, as the simulator writes
// it (`tests/test_scene_schema.py --update`).
export const QA_GREENHOUSE_PATH = "/qa/greenhouse";
export const QA_GREENHOUSE_SCENE_URL = "/scenes/qa-greenhouse.json";
export const QA_GREENHOUSE_VIEWS = ["outside", "aisle", "top", "section"] as const;
export type QaGreenhouseView = (typeof QA_GREENHOUSE_VIEWS)[number];

// Where each view stands, in metres from the greenhouse it shows.
const OUTSIDE_BACK_OFF_M = 9;
const OUTSIDE_RISE_M = 6;
const EYE_HEIGHT_M = 1.7;
const AISLE_FROM_THE_BACK_M = 1;
const TOP_RISE_M = 22;
// Straight down would leave "up" undefined; the top view leans a millimetre.
const TOP_LEAN_M = 0.001;
const SECTION_BACK_OFF_M = 11;

/** The view a QA address asks for, or the outside view by default; null for
 * a view there is not. */
export function qaGreenhouseView(search: string): QaGreenhouseView | null {
  const view = new URLSearchParams(search).get("view") ?? "outside";
  return (QA_GREENHOUSE_VIEWS as readonly string[]).includes(view)
    ? (view as QaGreenhouseView)
    : null;
}

interface Extent {
  length: number;
  width: number;
  height: number;
}

/** The greenhouse's length, width and height, from its bounds in the scene;
 * its floor corner stands at the world's origin, along the world's axes. */
export function greenhouseExtent(snapshot: SceneSnapshot): Extent | null {
  const bounds = snapshot.entities.find((entity) => entity.kind === "GREENHOUSE_BOUNDS");
  if (bounds?.shape.shape !== "box") {
    return null;
  }
  return { length: bounds.shape.size_x, width: bounds.shape.size_y, height: bounds.shape.size_z };
}

/** Where each view's camera stands and looks, for a greenhouse of `extent`. */
export function qaGreenhousePose(view: QaGreenhouseView, extent: Extent): CameraPose {
  const { length, width, height } = extent;
  const middle = { x: length / 2, y: width / 2, z: height / 2 };
  switch (view) {
    case "outside":
      // From beyond the back corner of its right side, looking at its middle.
      return {
        position: { x: length + OUTSIDE_BACK_OFF_M, y: -OUTSIDE_BACK_OFF_M, z: OUTSIDE_RISE_M },
        target: middle,
      };
    case "aisle":
      // Standing inside near the back, down the middle of the width, looking
      // along the house towards its front.
      return {
        position: { x: length - AISLE_FROM_THE_BACK_M, y: width / 2, z: EYE_HEIGHT_M },
        target: { x: 0, y: width / 2, z: EYE_HEIGHT_M },
      };
    case "top":
      return {
        position: { x: length / 2, y: width / 2 - TOP_LEAN_M, z: TOP_RISE_M },
        target: { x: length / 2, y: width / 2, z: 0 },
      };
    case "section":
      // Facing the cut at the middle of the length, from the side it opens.
      return {
        position: { x: length / 2 + SECTION_BACK_OFF_M, y: width / 2, z: height / 2 },
        target: middle,
      };
  }
}

/** The section view cuts the greenhouse across its length, at its middle,
 * keeping its front half. */
export function qaGreenhouseSection(view: QaGreenhouseView, extent: Extent): SectionPlane | null {
  return view === "section" ? { normal: { x: -1, y: 0, z: 0 }, distance: extent.length / 2 } : null;
}
