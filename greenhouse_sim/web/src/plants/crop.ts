import { DAY_S, daysEnded } from "../clock";
import { contractReader, loadJson } from "../loadJson";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { runParameters, type ScenarioRun, scenarioUrl } from "../scene/run";
import { CROP_PLANT_SCHEMA } from "./generated/cropPlantSchema";
import type { CropPlant as ServedPlant } from "./generated/cropPlantTypes";
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
 * organ or as the simple crop's plants are drawn (`GET
 * /api/scenarios/{id}/crop`): asked for as the climate is. */
export function cropUrl(run: ScenarioRun): string {
  return scenarioUrl(run.scenarioId, "crop", runParameters(atItsCropsDay(run)));
}

// The kinds a crop is drawn as whole, besides its organs: a plant, or a
// crop grown by area's canopy over a row.
const DRAWN_WHOLE: ReadonlySet<string> = new Set(["PLANT", "CANOPY"]);

/** The scene with the crop drawn as `crop` has it: every organ, every plant
 * drawn whole and every canopy the scene draws gives way to the crop's, on
 * the crop's day. */
export function withCrop(scene: SceneSnapshot, crop: SceneSnapshot): SceneSnapshot {
  return {
    ...scene,
    simulated_day: crop.simulated_day,
    entities: [
      ...scene.entities.filter(
        (entity) => typeof entity.properties.organ_id !== "string" && !DRAWN_WHOLE.has(entity.kind),
      ),
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
  /** How far it has developed, in °Cd. */
  thermalTime: number;
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

const readCropPlant = contractReader<ServedPlant>(
  CROP_PLANT_SCHEMA,
  "the plant is not what the viewer expects",
);

/** A plant of a run's crop, checked rather than trusted: with a day lived
 * for each of its days. */
export function parseCropPlant(body: unknown): CropPlant {
  const { days, structure, environments } = readCropPlant(body);
  if (environments.length !== days) {
    throw new Error("the plant's days are not what the viewer expects");
  }
  const tree = organTree(structure);
  return {
    plantId: tree.id,
    days,
    thermalTime: structure.thermal_time,
    tree,
    history: plantHistory(structure),
    environments: environments.map((day) => ({
      temperature: day.mean_temperature_c,
      light: day.par_mol_m2_day,
      co2: day.co2_ppm,
      water: day.water_status,
    })),
  };
}

/** Fetches a plant of a run's crop; every failure becomes `unavailable`. */
export async function loadCropPlant(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<CropPlantState> {
  const answer = await loadJson(url, parseCropPlant, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", plant: answer.value } : answer;
}
