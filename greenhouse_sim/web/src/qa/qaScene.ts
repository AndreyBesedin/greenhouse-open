import { MathUtils } from "three";

import { SUPPORTED_SCHEMA_VERSION } from "../scene/checkScene";
import type { Color, SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { QA_COLOUR_PROPERTY } from "./qaPage";

/**
 * The renderer's own QA scene, built in the viewer from a seed. It exercises
 * what the renderer draws (each kind of entity and shape, colours, rotations)
 * without the simulator, so its screenshot changes when the renderer changes
 * and not when a plant model does.
 */

export const QA_GREENHOUSE_ID = "qa_renderer";

// A numerical-recipes linear congruential generator: small, fast, and the
// same sequence in every browser for a given seed.
const LCG_MULTIPLIER = 1664525;
const LCG_INCREMENT = 1013904223;
const UINT32_RANGE = 4294967296;

const COLUMNS = 5;
const ROWS = 3;
// Plants stand on a grid from (0.6, 0.6) m, at these pitches along x and y.
const FIRST_PLANT_M = 0.6;
const COLUMN_PITCH_M = 0.7;
const ROW_PITCH_M = 0.9;
const GROUND_SIZE_X_M = 4;
const GROUND_SIZE_Y_M = 2.6;
const AXES_LENGTH_M = 1;
const STEM_RADIUS_M = 0.03;
const SHORTEST_STEM_M = 0.2;
const STEM_HEIGHT_SPREAD_M = 0.8;
// Each plant leans up to this far from upright, about a horizontal axis.
const MOST_LEAN_DEG = 15;
const MOST_LEAN_RAD = MathUtils.degToRad(MOST_LEAN_DEG);
const CENTIMETRES_PER_METRE = 100;

const GROUND_COLOR: Color = { r: 0.42, g: 0.33, b: 0.24 };
const AXES_COLOR: Color = { r: 0.5, g: 0.5, b: 0.5 };
const PLANT_COLOR: Color = { r: 0.2, g: 0.55, b: 0.24 };
const UPRIGHT = { w: 1, x: 0, y: 0, z: 0 };

/** Numbers in [0, 1), the same for the same seed. */
export function seededRandom(seed: number): () => number {
  let state = seed % UINT32_RANGE;
  return () => {
    state = (LCG_MULTIPLIER * state + LCG_INCREMENT) % UINT32_RANGE;
    return state / UINT32_RANGE;
  };
}

function plant(index: number, column: number, row: number, random: () => number): SceneEntity {
  const height = SHORTEST_STEM_M + random() * STEM_HEIGHT_SPREAD_M;
  const lean = random() * MOST_LEAN_RAD;
  const towards = random() * 2 * Math.PI;
  const entityId = `qa_plant_${String(index).padStart(2, "0")}`;
  return {
    entity_id: entityId,
    kind: "PLANT",
    transform: {
      position: {
        x: FIRST_PLANT_M + column * COLUMN_PITCH_M,
        y: FIRST_PLANT_M + row * ROW_PITCH_M,
        z: 0,
      },
      // A turn by `lean` about the horizontal axis pointing `towards`.
      rotation: {
        w: Math.cos(lean / 2),
        x: Math.sin(lean / 2) * Math.cos(towards),
        y: Math.sin(lean / 2) * Math.sin(towards),
        z: 0,
      },
    },
    shape: { shape: "cylinder", radius: STEM_RADIUS_M, height },
    color: PLANT_COLOR,
    label: entityId,
    properties: { [QA_COLOUR_PROPERTY]: height * CENTIMETRES_PER_METRE, row, column },
  };
}

export function qaScene(seed: number): SceneSnapshot {
  const random = seededRandom(seed);
  const plants: SceneEntity[] = [];
  for (let row = 0; row < ROWS; row += 1) {
    for (let column = 0; column < COLUMNS; column += 1) {
      plants.push(plant(plants.length + 1, column, row, random));
    }
  }
  return {
    schema_version: SUPPORTED_SCHEMA_VERSION,
    greenhouse_id: QA_GREENHOUSE_ID,
    simulated_day: 0,
    entities: [
      {
        entity_id: "qa_ground",
        kind: "GROUND",
        transform: {
          position: { x: GROUND_SIZE_X_M / 2, y: GROUND_SIZE_Y_M / 2, z: 0 },
          rotation: UPRIGHT,
        },
        shape: { shape: "plane", size_x: GROUND_SIZE_X_M, size_y: GROUND_SIZE_Y_M },
        color: GROUND_COLOR,
        label: "ground",
        properties: {},
      },
      {
        entity_id: "qa_axes",
        kind: "AXES",
        transform: { position: { x: 0, y: 0, z: 0 }, rotation: UPRIGHT },
        shape: { shape: "axes", length: AXES_LENGTH_M },
        color: AXES_COLOR,
        label: "world axes",
        properties: {},
      },
      ...plants,
    ],
  };
}
