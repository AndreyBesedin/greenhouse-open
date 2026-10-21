import { contractReader, loadJson } from "../loadJson";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import { GLAZING_SCHEMA } from "./generated/glazingSchema";
import type { GlazingAt, SurfaceTemperature } from "./generated/glazingTypes";

/** The glazing at a moment of a climate run, as the simulator sends it
 * (`GET /api/scenarios/{id}/climate/glazing`): at each glazed surface, the
 * mean air against it, its own temperature, and the heat it passes out of
 * the house (negative in). */
export type Glazing = GlazingAt;
export type { SurfaceTemperature };

export type GlazingState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; glazing: Glazing };

/** The properties a glazed surface's entity gains, for "Colour by" and the
 * inspector. */
export const SURFACE_TEMPERATURE = "surface_temperature_c";
export const GLASS_LOSS = "glass_loss_w";
const DECIMALS = 100;

/** Where a scenario's glazing at a moment of its climate run is published,
 * asked for as the climate is. */
export function glazingUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "climate/glazing", runParameters(run));
}

/** The glazing, checked rather than trusted. */
export const parseGlazing = contractReader<Glazing>(
  GLAZING_SCHEMA,
  "the glazing is not what the viewer expects",
);

/** Fetches the glazing at a moment; every failure becomes a state. */
export async function loadGlazing(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<GlazingState> {
  const answer = await loadJson(url, parseGlazing, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", glazing: answer.value } : answer;
}

function rounded(value: number): number {
  return Math.round(value * DECIMALS) / DECIMALS;
}

/** The scene with each glazed surface's temperature and the heat it passes
 * as its entity's properties, so that "Colour by" can shade the envelope by
 * them; the rest as it is. */
export function withGlazing(snapshot: SceneSnapshot, glazing: Glazing): SceneSnapshot {
  const bySurface = new Map(
    glazing.surfaces.map((surface) => [`${snapshot.greenhouse_id}_${surface.surface_id}`, surface]),
  );
  return {
    ...snapshot,
    entities: snapshot.entities.map((entity) => {
      const surface = bySurface.get(entity.entity_id);
      return surface === undefined
        ? entity
        : {
            ...entity,
            properties: {
              ...entity.properties,
              [SURFACE_TEMPERATURE]: rounded(surface.surface_c),
              [GLASS_LOSS]: Math.round(surface.loss_w),
            },
          };
    }),
  };
}
