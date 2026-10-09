import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { pairsText, type ScheduledCommand, scheduleText, weatherParameter } from "../scene/source";

/** A glazed surface at a moment: the mean air against it, its own
 * temperature, and the heat it passes out of the house (negative in). */
export interface SurfaceTemperature {
  surface_id: string;
  air_c: number;
  surface_c: number;
  loss_w: number;
}

/** The glazing at a moment of a climate run, as the simulator sends it
 * (`GET /api/scenarios/{id}/climate/glazing`). */
export interface Glazing {
  time_s: number;
  outside_c: number;
  u_w_m2k: number;
  surfaces: SurfaceTemperature[];
}

export type GlazingState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; glazing: Glazing };

/** The properties a glazed surface's entity gains, for "Colour by" and the
 * inspector. */
export const SURFACE_TEMPERATURE = "surface_temperature_c";
export const GLASS_LOSS = "glass_loss_w";
const SURFACE_NUMBERS = ["air_c", "surface_c", "loss_w"] as const;
const DECIMALS = 100;

/** Where a scenario's glazing at a moment of its climate run is published,
 * asked for as the climate is. */
export function glazingUrl(
  scenarioId: string,
  run: {
    layout?: string | undefined;
    levels?: Readonly<Record<string, number>> | undefined;
    openings?: Readonly<Record<string, number>> | undefined;
    schedule?: readonly ScheduledCommand[] | undefined;
    time?: number | undefined;
    weather?: string | undefined;
  },
): string {
  const parts = [
    ...(run.layout === undefined ? [] : [`layout=${encodeURIComponent(run.layout)}`]),
    ...(pairsText(run.levels) === "" ? [] : [`set=${pairsText(run.levels)}`]),
    ...(pairsText(run.openings) === "" ? [] : [`open=${pairsText(run.openings)}`]),
    ...(scheduleText(run.schedule) === "" ? [] : [`schedule=${scheduleText(run.schedule)}`]),
    ...(run.time === undefined || run.time === 0 ? [] : [`t=${run.time}`]),
    ...weatherParameter(run.weather),
  ];
  const query = parts.length === 0 ? "" : `?${parts.join("&")}`;
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/climate/glazing${query}`;
}

function isSurface(value: unknown): value is SurfaceTemperature {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const fields = value as Record<string, unknown>;
  return (
    typeof fields.surface_id === "string" &&
    SURFACE_NUMBERS.every((name) => typeof fields[name] === "number")
  );
}

/** The glazing, checked rather than trusted. */
export function parseGlazing(body: unknown): Glazing {
  if (typeof body !== "object" || body === null) {
    throw new Error("the glazing is not what the viewer expects");
  }
  const fields = body as Record<string, unknown>;
  if (
    typeof fields.time_s !== "number" ||
    typeof fields.outside_c !== "number" ||
    typeof fields.u_w_m2k !== "number" ||
    !Array.isArray(fields.surfaces) ||
    !fields.surfaces.every(isSurface)
  ) {
    throw new Error("the glazing is not what the viewer expects");
  }
  return {
    time_s: fields.time_s,
    outside_c: fields.outside_c,
    u_w_m2k: fields.u_w_m2k,
    surfaces: fields.surfaces,
  };
}

/** Fetches the glazing at a moment; every failure becomes a state. */
export async function loadGlazing(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<GlazingState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", glazing: parseGlazing(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
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
