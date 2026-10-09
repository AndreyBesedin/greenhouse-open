import { inWorld } from "../debug/dimensions";
import type { OverlayPrimitive } from "../debug/overlays";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { pairsText, type ScheduledCommand, scheduleText, weatherParameter } from "../scene/source";

/** What an open door or vent passes at a moment: its net flow into the
 * house (m³/s, negative out), and what it exchanges each way besides. */
export interface OpeningFlow {
  opening_id: string;
  net_m3_s: number;
  exchange_m3_s: number;
}

/** What each open door and vent passes at a moment of a climate run, as the
 * simulator sends it (`GET /api/scenarios/{id}/climate/openings`). */
export interface OpeningsAt {
  time_s: number;
  openings: OpeningFlow[];
}

export type OpeningsState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; openings: OpeningsAt };

/** The properties an opening's entity gains, for "Colour by" and the
 * inspector. */
export const NET_FLOW = "flow_in_m3_s";
export const EXCHANGE = "exchange_m3_s";
const DECIMALS = 100;
// The arrow at an opening: a metre long for each cubic metre a second, from
// half a metre to three, beside the opening.
const ARROW_M_PER_M3_S = 1;
const SHORTEST_ARROW_M = 0.5;
const LONGEST_ARROW_M = 3;
const ARROW_CLEARANCE_M = 0.2;
const FLOW_DECIMALS = 2;
export const FLOW_COLOR = "#16a085";

/** Where what the openings pass at a moment of a climate run is published,
 * asked for as the climate is. */
export function openingsUrl(
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
  return `/api/scenarios/${encodeURIComponent(scenarioId)}/climate/openings${query}`;
}

function isFlow(value: unknown): value is OpeningFlow {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const fields = value as Record<string, unknown>;
  return (
    typeof fields.opening_id === "string" &&
    typeof fields.net_m3_s === "number" &&
    typeof fields.exchange_m3_s === "number"
  );
}

/** What the openings pass, checked rather than trusted. */
export function parseOpenings(body: unknown): OpeningsAt {
  if (typeof body !== "object" || body === null) {
    throw new Error("the openings are not what the viewer expects");
  }
  const fields = body as Record<string, unknown>;
  if (
    typeof fields.time_s !== "number" ||
    !Array.isArray(fields.openings) ||
    !fields.openings.every(isFlow)
  ) {
    throw new Error("the openings are not what the viewer expects");
  }
  return { time_s: fields.time_s, openings: fields.openings };
}

/** Fetches what the openings pass at a moment; every failure becomes a
 * state. */
export async function loadOpenings(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<OpeningsState> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", openings: parseOpenings(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}

function rounded(value: number): number {
  return Math.round(value * DECIMALS) / DECIMALS;
}

/** The scene with each open door's and vent's flows as its entity's
 * properties, so that "Colour by" can shade the openings by them. */
export function withOpeningFlows(snapshot: SceneSnapshot, at: OpeningsAt): SceneSnapshot {
  const byOpening = new Map(
    at.openings.map((flow) => [`${snapshot.greenhouse_id}_${flow.opening_id}`, flow]),
  );
  return {
    ...snapshot,
    entities: snapshot.entities.map((entity) => {
      const flow = byOpening.get(entity.entity_id);
      return flow === undefined
        ? entity
        : {
            ...entity,
            properties: {
              ...entity.properties,
              [NET_FLOW]: rounded(flow.net_m3_s),
              [EXCHANGE]: rounded(flow.exchange_m3_s),
            },
          };
    }),
  };
}

/** A flow through an opening in words: "2.06 m³/s in". */
export function describeFlow(netM3S: number): string {
  return `${Math.abs(netM3S).toFixed(FLOW_DECIMALS)} m³/s ${netM3S > 0 ? "in" : "out"}`;
}

/**
 * An arrow at each opening a net flow passes through: from outside, pointing
 * in, where air enters, and from inside, pointing out, where it leaves, a
 * metre long for each cubic metre a second, labelled with the flow.
 */
export function openingFlowOverlays(snapshot: SceneSnapshot, at: OpeningsAt): OverlayPrimitive[] {
  const entities = new Map(snapshot.entities.map((entity) => [entity.entity_id, entity]));
  return at.openings.flatMap((flow): OverlayPrimitive[] => {
    const entity = entities.get(`${snapshot.greenhouse_id}_${flow.opening_id}`);
    if (entity === undefined || flow.net_m3_s === 0) {
      return [];
    }
    const centre = inWorld(entity.transform, { x: 0, y: 0, z: 0 });
    const ahead = inWorld(entity.transform, { x: 0, y: 0, z: 1 });
    const inward = { x: ahead.x - centre.x, y: ahead.y - centre.y, z: ahead.z - centre.z };
    const length = Math.min(
      Math.max(Math.abs(flow.net_m3_s) * ARROW_M_PER_M3_S, SHORTEST_ARROW_M),
      LONGEST_ARROW_M,
    );
    const entering = flow.net_m3_s > 0;
    const back = entering ? -(length + ARROW_CLEARANCE_M) : length + ARROW_CLEARANCE_M;
    const origin = {
      x: centre.x + inward.x * back,
      y: centre.y + inward.y * back,
      z: centre.z + inward.z * back,
    };
    const direction = entering ? inward : { x: -inward.x, y: -inward.y, z: -inward.z };
    return [
      {
        id: `${flow.opening_id}-flow`,
        kind: "arrow",
        origin,
        direction,
        length,
        color: FLOW_COLOR,
      },
      {
        id: `${flow.opening_id}-flow-label`,
        kind: "label",
        position: origin,
        text: describeFlow(flow.net_m3_s),
      },
    ];
  });
}
