import type { CameraPose } from "../camera";
import type { Slice } from "../fields/display";

// The P04 final QA, `airflow-box`: the airflow QA scenario's scene and its
// air as OpenFOAM solved it, as the simulator writes them
// (`tests/test_airflow_qa.py --update`), drawn from fixed views.
export const QA_AIRFLOW_PATH = "/qa/airflow-box";
export const QA_AIRFLOW_SCENE_URL = "/scenes/qa-airflow-box.json";
export const QA_AIRFLOW_FIELD_URL = "/fields/qa-airflow-box-cfd.json";
export const QA_AIRFLOW_VIEWS = ["vectors", "slice"] as const;
export type QaAirflowView = (typeof QA_AIRFLOW_VIEWS)[number];

// The house is 12 m long and 6.4 m wide, its block halfway along it and 1.5 m
// high. The vectors are seen from beside and above the house, looking at the
// middle of its length at the block's top; the slice from straight above,
// leaning a millimetre so that "up" on screen is defined.
const MIDDLE = { x: 6, y: 3.2 };
const BLOCK_TOP_M = 1.5;
const BESIDE_M = 8;
const ABOVE_M = 9;
const TOP_RISE_M = 12;
const TOP_LEAN_M = 0.001;
// The slice runs through the block at half its height.
export const QA_AIRFLOW_SLICE: Slice = { quantity: "speed", axis: "z", position: BLOCK_TOP_M / 2 };

export const QA_AIRFLOW_POSES: Record<QaAirflowView, CameraPose> = {
  vectors: {
    position: { x: MIDDLE.x, y: -BESIDE_M, z: ABOVE_M },
    target: { x: MIDDLE.x, y: MIDDLE.y, z: BLOCK_TOP_M },
  },
  slice: {
    position: { x: MIDDLE.x, y: MIDDLE.y - TOP_LEAN_M, z: TOP_RISE_M },
    target: { x: MIDDLE.x, y: MIDDLE.y, z: 0 },
  },
};

/** The view a QA address asks for, or the vectors by default; null for a
 * view there is not. */
export function qaAirflowView(search: string): QaAirflowView | null {
  const view = new URLSearchParams(search).get("view") ?? "vectors";
  return (QA_AIRFLOW_VIEWS as readonly string[]).includes(view) ? (view as QaAirflowView) : null;
}
