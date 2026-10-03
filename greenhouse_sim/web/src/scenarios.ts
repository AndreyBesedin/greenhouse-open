/** A scenario as the simulator's local API lists it (`GET /api/scenarios`). */
export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  plants: number;
  duration_days: number;
}

export type ScenariosState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; scenarios: ScenarioSummary[] };

/** The scenarios in a response body, checked rather than trusted. */
export function parseScenarios(body: unknown): ScenarioSummary[] {
  if (!Array.isArray(body)) {
    throw new Error("expected a list of scenarios");
  }
  return body.map((item: unknown, index) => {
    if (!isScenarioSummary(item)) {
      throw new Error(`scenario ${index} is not a scenario summary`);
    }
    return item;
  });
}

function isScenarioSummary(value: unknown): value is ScenarioSummary {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const fields = value as Record<string, unknown>;
  return (
    typeof fields.id === "string" &&
    typeof fields.name === "string" &&
    typeof fields.description === "string" &&
    Number.isInteger(fields.plants) &&
    Number.isInteger(fields.duration_days)
  );
}

/** Asks the simulator for its scenarios; any failure becomes `unavailable`. */
export async function loadScenarios(fetchFn: typeof fetch = fetch): Promise<ScenariosState> {
  try {
    const response = await fetchFn("/api/scenarios");
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", scenarios: parseScenarios(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}
