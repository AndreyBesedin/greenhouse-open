import { weatherParameter } from "../scene/source";

// PAR is shown to whole micromoles, a day's light to tenths of a mole.
const PAR_DECIMALS = 0;
const INTEGRAL_DECIMALS = 1;

/** The light on each of a scenario's plants at a moment of a run, as the
 * simulator sends it (`GET /api/scenarios/{id}/climate/plants`): each
 * plant's PAR then, in µmol/m²/s, and its daily light integral on the run's
 * first day, in mol/m²/d, by plant. */
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
 * with one of its layouts and under a weather, or its own. */
export function plantsLightUrl(
  scenarioId: string,
  time: number,
  weather?: string,
  layout?: string,
): string {
  const parts = [
    ...(layout === undefined ? [] : [`layout=${encodeURIComponent(layout)}`]),
    ...(time === 0 ? [] : [`t=${time}`]),
    ...weatherParameter(weather),
  ];
  const query = parts.length === 0 ? "" : `?${parts.join("&")}`;
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/climate/plants${query}`;
}

function isNumbers(value: unknown): value is Record<string, number> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((entry) => typeof entry === "number")
  );
}

/** A plants' light response, checked rather than trusted. */
export function parsePlantsLight(body: unknown): PlantsLight {
  if (typeof body !== "object" || body === null) {
    throw new Error("the plants' light is not what the viewer expects");
  }
  const { time_s, par_umol_m2_s, daily_light_integral_mol_m2_d } = body as Record<string, unknown>;
  if (
    typeof time_s !== "number" ||
    !isNumbers(par_umol_m2_s) ||
    !isNumbers(daily_light_integral_mol_m2_d)
  ) {
    throw new Error("the plants' light is not what the viewer expects");
  }
  return { timeS: time_s, par: par_umol_m2_s, dailyLight: daily_light_integral_mol_m2_d };
}

/** Fetches the light on a scenario's plants at a moment of a run; every
 * failure becomes `unavailable`. */
export async function loadPlantsLight(
  scenarioId: string,
  time: number,
  weather: string | undefined,
  layout: string | undefined,
  fetchFn: typeof fetch = fetch,
): Promise<PlantsLightState> {
  try {
    const response = await fetchFn(plantsLightUrl(scenarioId, time, weather, layout));
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", light: parsePlantsLight(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
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
