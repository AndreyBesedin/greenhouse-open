import { contractReader, loadJson } from "../loadJson";
import { PERCENT } from "../units";
import { LAB_ENVIRONMENTS_SCHEMA } from "./generated/labEnvironmentsSchema";
import type { LabEnvironments } from "./generated/labEnvironmentsTypes";

/** One of the plant lab's environments, as the simulator describes it
 * (`GET /api/plants/environments`): what a plant there experiences each day. */
export interface LabEnvironment {
  meanTemperatureC: number;
  parMolM2Day: number;
  co2Ppm: number;
  waterStatus: number;
}

export type EnvironmentsState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; environments: Record<string, LabEnvironment> };

export const PLANT_LAB_ENVIRONMENTS_URL = "/api/plants/environments";

const readEnvironments = contractReader<LabEnvironments>(
  LAB_ENVIRONMENTS_SCHEMA,
  "the environments are not what the viewer expects",
);

/** The lab's environments by name, checked rather than trusted. */
export function labEnvironments(body: unknown): Record<string, LabEnvironment> {
  return Object.fromEntries(
    Object.entries(readEnvironments(body)).map(([name, environment]) => [
      name,
      {
        meanTemperatureC: environment.mean_temperature_c,
        parMolM2Day: environment.par_mol_m2_day,
        co2Ppm: environment.co2_ppm,
        waterStatus: environment.water_status,
      },
    ]),
  );
}

/** An environment in words: temperature, light, CO₂ and water. */
export function describeEnvironment(environment: LabEnvironment): string {
  const water = Math.round(environment.waterStatus * PERCENT);
  return `${environment.meanTemperatureC} °C, ${environment.parMolM2Day} mol/m²/d PAR, ${environment.co2Ppm} ppm CO₂, water ${water}%`;
}

/** Asks the plant lab for its environments; any failure becomes
 * `unavailable`. */
export async function loadLabEnvironments(
  fetchFn: typeof fetch = fetch,
): Promise<EnvironmentsState> {
  const answer = await loadJson(PLANT_LAB_ENVIRONMENTS_URL, labEnvironments, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", environments: answer.value } : answer;
}
