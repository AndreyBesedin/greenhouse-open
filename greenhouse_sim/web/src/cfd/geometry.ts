import { contractCheck, loadJson } from "../loadJson";
import { CFD_GEOMETRY_SCHEMA } from "./generated/geometrySchema";
import type { CfdGeometry } from "./generated/geometryTypes";

const checkGeometry = contractCheck<CfdGeometry>(CFD_GEOMETRY_SCHEMA, "the geometry");

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
  const checked = checkGeometry(body);
  return checked.ok ? { ok: true, geometry: checked.value } : checked;
}

/** Fetches and checks a CFD geometry; every failure becomes a state to show. */
export async function loadCfdGeometry(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<CfdGeometryState> {
  const answer = await loadJson(url, checkCfdGeometry, fetchFn);
  if (answer.status !== "loaded") {
    return answer;
  }
  const check = answer.value;
  return check.ok
    ? { status: "loaded", geometry: check.geometry }
    : { status: "rejected", problems: check.problems };
}
