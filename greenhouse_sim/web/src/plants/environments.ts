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
const PERCENT = 100;

function numberIn(fields: Record<string, unknown>, name: string, environment: string): number {
  const value = fields[name];
  if (typeof value !== "number") {
    throw new Error(`${environment}'s ${name} is not a number`);
  }
  return value;
}

/** The lab's environments by name, checked rather than trusted. */
export function labEnvironments(body: unknown): Record<string, LabEnvironment> {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    throw new Error("the environments are not an object");
  }
  return Object.fromEntries(
    Object.entries(body).map(([name, value]) => {
      if (typeof value !== "object" || value === null) {
        throw new Error(`${name} is not an environment`);
      }
      const fields = value as Record<string, unknown>;
      return [
        name,
        {
          meanTemperatureC: numberIn(fields, "mean_temperature_c", name),
          parMolM2Day: numberIn(fields, "par_mol_m2_day", name),
          co2Ppm: numberIn(fields, "co2_ppm", name),
          waterStatus: numberIn(fields, "water_status", name),
        },
      ];
    }),
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
  try {
    const response = await fetchFn(PLANT_LAB_ENVIRONMENTS_URL);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", environments: labEnvironments(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}
