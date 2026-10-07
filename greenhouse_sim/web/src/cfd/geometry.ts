import Ajv2020 from "ajv/dist/2020";

import { CFD_GEOMETRY_SCHEMA } from "./generated/geometrySchema";
import type { CfdGeometry } from "./generated/geometryTypes";

const validate = new Ajv2020({ allErrors: true, strict: true }).compile<CfdGeometry>(
  CFD_GEOMETRY_SCHEMA,
);

export type CfdGeometryState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "rejected"; problems: string[] }
  | { status: "loaded"; geometry: CfdGeometry };

/** Where a scenario's CFD geometry is published
 * (`GET /api/scenarios/{id}/cfd/geometry`), changed as its scene is: `changes`
 * is the scene's own query, `?open=door_1:1` or empty. */
export function cfdGeometryUrl(scenarioId: string, changes: string): string {
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/cfd/geometry${changes}`;
}

/** A published CFD geometry checked against the schema the simulator
 * publishes, rather than trusted. */
export function checkCfdGeometry(
  body: unknown,
): { ok: true; geometry: CfdGeometry } | { ok: false; problems: string[] } {
  if (validate(body)) {
    return { ok: true, geometry: body };
  }
  const problems = (validate.errors ?? []).map(
    (error) => `${error.instancePath || "the geometry"} ${error.message ?? "is not valid"}`,
  );
  return { ok: false, problems };
}

/** Fetches and checks a CFD geometry; every failure becomes a state to show. */
export async function loadCfdGeometry(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<CfdGeometryState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    const check = checkCfdGeometry(await response.json());
    return check.ok
      ? { status: "loaded", geometry: check.geometry }
      : { status: "rejected", problems: check.problems };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}
