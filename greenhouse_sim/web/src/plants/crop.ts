import { DAY_S, daysEnded } from "../clock";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { runParameters, type ScenarioRun, scenarioUrl } from "../scene/run";
import { type OrganNode, organTree, type PlantEvent, plantHistory } from "./structure";

/** How a scenario whose runs grow its crop organ by organ says so
 * (`ScenarioSummary.crop_model`). */
export const ORGAN_CROP = "organ";

/** A run asked for at the start of the days its crop has lived by its
 * moment, so that every moment of a day asks for the same crop. */
function atItsCropsDay(run: ScenarioRun): ScenarioRun {
  return { ...run, time: daysEnded(run.time ?? 0) * DAY_S };
}

/** Where a scenario's crop at the moment of a run is published, organ by
 * organ (`GET /api/scenarios/{id}/crop`): asked for as the climate is. */
export function cropUrl(run: ScenarioRun): string {
  return scenarioUrl(run.scenarioId, "crop", runParameters(atItsCropsDay(run)));
}

/** The scene with the crop drawn as `crop` has it: every organ the scene
 * draws gives way to the crop's, on the crop's day. */
export function withCrop(scene: SceneSnapshot, crop: SceneSnapshot): SceneSnapshot {
  return {
    ...scene,
    simulated_day: crop.simulated_day,
    entities: [
      ...scene.entities.filter((entity) => typeof entity.properties.organ_id !== "string"),
      ...crop.entities,
    ],
  };
}

/** What a plant experienced on one day of a run: the house's mean air
 * temperature (°C) and CO₂ (ppm), its own daily light integral (mol/m²/d),
 * and its root zone's water status, from 0 to 1. */
export interface PlantDay {
  temperature: number;
  light: number;
  co2: number;
  water: number;
}

/** One plant of a scenario's crop at a moment of a run, once it has lived
 * the run's first `days` days: its structure, its history, and each day it
 * lived (`GET /api/scenarios/{id}/crop/{plant}`). */
export interface CropPlant {
  plantId: string;
  days: number;
  tree: OrganNode;
  history: PlantEvent[];
  environments: PlantDay[];
}

export type CropPlantState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; plant: CropPlant };

/** Where one plant of a scenario's crop at the moment of a run is
 * published, asked for as its crop is. */
export function cropPlantUrl(run: ScenarioRun, plantId: string): string {
  return scenarioUrl(
    run.scenarioId,
    `crop/${encodeURIComponent(plantId)}`,
    runParameters(atItsCropsDay(run)),
  );
}

function plantDay(value: unknown): PlantDay {
  if (typeof value !== "object" || value === null) {
    throw new Error("a plant's day is not an object");
  }
  const { mean_temperature_c, par_mol_m2_day, co2_ppm, water_status } = value as Record<
    string,
    unknown
  >;
  if (
    typeof mean_temperature_c !== "number" ||
    typeof par_mol_m2_day !== "number" ||
    typeof co2_ppm !== "number" ||
    typeof water_status !== "number"
  ) {
    throw new Error("a plant's day is not what the viewer expects");
  }
  return {
    temperature: mean_temperature_c,
    light: par_mol_m2_day,
    co2: co2_ppm,
    water: water_status,
  };
}

/** A plant of a run's crop, checked rather than trusted. */
export function parseCropPlant(body: unknown): CropPlant {
  if (typeof body !== "object" || body === null) {
    throw new Error("the plant is not what the viewer expects");
  }
  const { days, structure, environments } = body as Record<string, unknown>;
  if (!Number.isInteger(days) || !Array.isArray(environments) || environments.length !== days) {
    throw new Error("the plant's days are not what the viewer expects");
  }
  const tree = organTree(structure);
  return {
    plantId: tree.id,
    days: days as number,
    tree,
    history: plantHistory(structure),
    environments: environments.map(plantDay),
  };
}

/** Fetches a plant of a run's crop; every failure becomes `unavailable`. */
export async function loadCropPlant(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<CropPlantState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", plant: parseCropPlant(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}
