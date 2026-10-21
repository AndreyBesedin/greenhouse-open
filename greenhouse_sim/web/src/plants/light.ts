import { contractReader, loadJson } from "../loadJson";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import { PLANTS_LIGHT_SCHEMA } from "./generated/plantsLightSchema";
import type { PlantsLight as ServedLight } from "./generated/plantsLightTypes";

// PAR is shown to whole micromoles, a day's light to tenths of a mole.
const PAR_DECIMALS = 0;
const INTEGRAL_DECIMALS = 1;

/** The light on each of a scenario's plants at a moment of a run, as the
 * simulator sends it (`GET /api/scenarios/{id}/climate/plants`): each
 * plant's PAR then, in µmol/m²/s, and its daily light integral on the
 * moment's day, in mol/m²/d, by plant. */
export interface PlantsLight {
  timeS: number;
  par: Record<string, number>;
  dailyLight: Record<string, number>;
}

export type PlantsLightState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; light: PlantsLight };

/** Where the light on a scenario's plants at a moment of a run is published,
 * asked for as the climate is: its crowns grow with a crop grown organ by
 * organ, as the run's air grows it. */
export function plantsLightUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "climate/plants", runParameters(run));
}

const readLight = contractReader<ServedLight>(
  PLANTS_LIGHT_SCHEMA,
  "the plants' light is not what the viewer expects",
);

/** A plants' light response, checked rather than trusted. */
export function parsePlantsLight(body: unknown): PlantsLight {
  const light = readLight(body);
  return {
    timeS: light.time_s,
    par: light.par_umol_m2_s,
    dailyLight: light.daily_light_integral_mol_m2_d,
  };
}

/** Fetches the light on a scenario's plants at a moment of a run, from its
 * `plantsLightUrl`; every failure becomes `unavailable`. */
export async function loadPlantsLight(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<PlantsLightState> {
  const answer = await loadJson(url, parsePlantsLight, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", light: answer.value } : answer;
}

/** A plant's light in words: its PAR at the moment, "512 µmol/m²/s", and its
 * day's, "24.3 mol/m²/d"; null for a plant the light does not know. */
export function describePlantLight(
  light: PlantsLight,
  plantId: string,
): { now: string; day: string } | null {
  const now = light.par[plantId];
  const day = light.dailyLight[plantId];
  if (now === undefined || day === undefined) {
    return null;
  }
  return {
    now: `${now.toFixed(PAR_DECIMALS)} µmol/m²/s`,
    day: `${day.toFixed(INTEGRAL_DECIMALS)} mol/m²/d`,
  };
}
