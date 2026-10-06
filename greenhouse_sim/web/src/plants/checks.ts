/** What the simulator's lab finds wrong with each of its plants on a run's
 * day (`GET /api/plants/checks`): the structure's rules each breaks, and
 * anything it did since the day before that a plant cannot. */
export type ChecksState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; day: number; problems: Record<string, string[]> };

export const PLANT_LAB_CHECKS_URL = "/api/plants/checks";

/** The checks, checked rather than trusted. */
export function labChecks(body: unknown): { day: number; problems: Record<string, string[]> } {
  if (typeof body !== "object" || body === null) {
    throw new Error("the checks are not an object");
  }
  const { day, problems } = body as Record<string, unknown>;
  if (typeof day !== "number" || typeof problems !== "object" || problems === null) {
    throw new Error("the checks have no day or no problems");
  }
  const byPlant = Object.entries(problems).map(([plantId, found]) => {
    if (!Array.isArray(found) || !found.every((problem) => typeof problem === "string")) {
      throw new Error(`${plantId}'s problems are not a list of text`);
    }
    return [plantId, found as string[]] as const;
  });
  return { day, problems: Object.fromEntries(byPlant) };
}

/** Asks the lab for its checks on a run, as `labRunQuery` writes it; any
 * failure becomes `unavailable`. */
export async function loadLabChecks(
  runQuery: string,
  fetchFn: typeof fetch = fetch,
): Promise<ChecksState> {
  try {
    const response = await fetchFn(`${PLANT_LAB_CHECKS_URL}?${runQuery}`);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", ...labChecks(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}
