import type { Color, SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { SUPPORTED_SCHEMA_VERSION } from "../scene/schemaVersion";
import { seededRandom } from "./qaScene";

/**
 * A dense, greenhouse-like field for measuring the renderer: double rows of
 * upright plants of seeded heights, centred on the origin. Built in the
 * viewer, so it needs no simulator and is the same on every visit.
 */

export const DEFAULT_STRESS_PLANTS = 10_000;
export const MAX_STRESS_PLANTS = 100_000;
const STRESS_SEED = 7;

// Rows run along x, a plant every 40 cm. Rows come in pairs 50 cm apart,
// with 1.6 m between the middles of neighbouring pairs, as a path between
// double rows would leave.
export const PLANTS_PER_ROW = 100;
export const PLANT_PITCH_M = 0.4;
export const PAIR_SPACING_M = 1.6;
export const ROW_GAP_IN_PAIR_M = 0.5;
const ROWS_PER_PAIR = 2;
// The ground reaches this far beyond the outermost plants.
const GROUND_MARGIN_M = 1;
const AXES_LENGTH_M = 1;
const STEM_RADIUS_M = 0.03;
const SHORTEST_STEM_M = 0.3;
const STEM_HEIGHT_SPREAD_M = 0.9;
const CENTIMETRES_PER_METRE = 100;

const GROUND_COLOR: Color = { r: 0.42, g: 0.33, b: 0.24 };
const AXES_COLOR: Color = { r: 0.5, g: 0.5, b: 0.5 };
const PLANT_COLOR: Color = { r: 0.2, g: 0.55, b: 0.24 };
const UPRIGHT = { w: 1, x: 0, y: 0, z: 0 };

/** Where the plant in `column` of `row` stands, for a field of `rows` rows. */
export function stressPlantPosition(
  column: number,
  row: number,
  rows: number,
): { x: number; y: number; z: number } {
  const pairs = Math.ceil(rows / ROWS_PER_PAIR);
  const pair = Math.floor(row / ROWS_PER_PAIR);
  const side = row % ROWS_PER_PAIR;
  return {
    x: (column - (PLANTS_PER_ROW - 1) / 2) * PLANT_PITCH_M,
    y: (pair - (pairs - 1) / 2) * PAIR_SPACING_M + (side - 1 / 2) * ROW_GAP_IN_PAIR_M,
    z: 0,
  };
}

// Enough digits for the largest field, so identifiers sort in planting order.
const ID_DIGITS = String(MAX_STRESS_PLANTS).length;

export function stressPlantId(index: number): string {
  return `stress_plant_${String(index).padStart(ID_DIGITS, "0")}`;
}

export function stressScene(plantCount: number): SceneSnapshot {
  const random = seededRandom(STRESS_SEED);
  const rows = Math.ceil(plantCount / PLANTS_PER_ROW);
  const plants: SceneEntity[] = [];
  for (let index = 0; index < plantCount; index += 1) {
    const height = SHORTEST_STEM_M + random() * STEM_HEIGHT_SPREAD_M;
    const row = Math.floor(index / PLANTS_PER_ROW);
    const column = index % PLANTS_PER_ROW;
    plants.push({
      entity_id: stressPlantId(index + 1),
      kind: "PLANT",
      transform: { position: stressPlantPosition(column, row, rows), rotation: UPRIGHT },
      shape: { shape: "cylinder", radius: STEM_RADIUS_M, height },
      color: PLANT_COLOR,
      label: null,
      properties: { height_cm: height * CENTIMETRES_PER_METRE, row, column },
    });
  }
  const pairs = Math.ceil(rows / ROWS_PER_PAIR);
  return {
    schema_version: SUPPORTED_SCHEMA_VERSION,
    greenhouse_id: "stress",
    simulated_day: 0,
    entities: [
      {
        entity_id: "stress_ground",
        kind: "GROUND",
        transform: { position: { x: 0, y: 0, z: 0 }, rotation: UPRIGHT },
        shape: {
          shape: "plane",
          size_x: PLANTS_PER_ROW * PLANT_PITCH_M + 2 * GROUND_MARGIN_M,
          size_y: pairs * PAIR_SPACING_M + 2 * GROUND_MARGIN_M,
        },
        color: GROUND_COLOR,
        label: "ground",
        properties: {},
      },
      {
        entity_id: "stress_axes",
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

/** The plant count a stress address asks for: a whole number up to the
 * maximum, or the default. */
export function stressPlants(value: string | null): number {
  if (value === null || !/^\d+$/.test(value)) {
    return DEFAULT_STRESS_PLANTS;
  }
  return Math.min(Math.max(Number(value), 1), MAX_STRESS_PLANTS);
}
