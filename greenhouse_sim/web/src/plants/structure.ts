import type { LabRun } from "./lab";

/** One organ of a plant's structure, with the organs attached to it, as the
 * simulator's plant lab describes them (`GET /api/plants/structure`). */
export interface OrganNode {
  id: string;
  kind: "plant" | "stem" | "phytomer" | "internode" | "leaf" | "truss" | "flower" | "fruit";
  /** Whether the viewer draws it, and so can select it in the view. */
  drawn: boolean;
  /** How far it has developed, and its stage, in words. */
  detail: string;
  children: OrganNode[];
}

/** Something done to the plant, or asked of it and refused. */
export interface PlantEvent {
  thermalTime: number;
  applied: boolean;
  /** What it did, or why it was refused. */
  note: string;
}

export type StructureState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; tree: OrganNode; history: PlantEvent[] };

export const PLANT_LAB_STRUCTURE_URL = "/api/plants/structure";

type Fields = Record<string, unknown>;

function fields(value: unknown, what: string): Fields {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${what} is not an object`);
  }
  return value as Fields;
}

function text(value: Fields, name: string): string {
  const found = value[name];
  if (typeof found !== "string") {
    throw new Error(`${name} is not text`);
  }
  return found;
}

function number(value: Fields, name: string): number {
  const found = value[name];
  if (typeof found !== "number") {
    throw new Error(`${name} is not a number`);
  }
  return found;
}

function list(value: Fields, name: string): unknown[] {
  const found = value[name];
  if (!Array.isArray(found)) {
    throw new Error(`${name} is not a list`);
  }
  return found;
}

// The stages in which the view draws a flower, and a fruit: a set flower is
// drawn as its fruit, and an aborted flower or fruit has dropped.
const DRAWN_FLOWER_STAGES: ReadonlySet<unknown> = new Set(["bud", "open"]);
const DRAWN_FRUIT_STAGES: ReadonlySet<unknown> = new Set(["attached"]);
const PERCENT = 100;

/** An organ's thermal age, its stage if it has one, and how ripe it is if
 * it has started to ripen. */
function describe(organ: Fields, thermalTime: number): string {
  const age = `${Math.round(thermalTime - number(organ, "born_tt"))} °Cd`;
  const stage = typeof organ.stage === "string" ? `, ${organ.stage}` : "";
  const ripeness = organ.ripeness;
  const ripe =
    typeof ripeness === "number" && ripeness > 0 ? `, ${Math.round(ripeness * PERCENT)}% ripe` : "";
  return `${age}${stage}${ripe}`;
}

/** The plant's structure as a tree, checked rather than trusted. */
export function organTree(body: unknown): OrganNode {
  const plant = fields(body, "the plant");
  const thermalTime = number(plant, "thermal_time");
  const stem = fields(plant.stem, "the stem");
  const node = (
    organ: Fields,
    id: string,
    kind: OrganNode["kind"],
    drawn: boolean,
    children: OrganNode[] = [],
  ): OrganNode => ({ id, kind, drawn, detail: describe(organ, thermalTime), children });

  const phytomers = list(stem, "phytomers").map((value) => {
    const phytomer = fields(value, "a phytomer");
    const internode = fields(phytomer.internode, "an internode");
    const leaf = fields(phytomer.leaf, "a leaf");
    const children = [
      node(internode, text(internode, "internode_id"), "internode", true),
      node(leaf, text(leaf, "leaf_id"), "leaf", leaf.stage !== "removed"),
    ];
    if (phytomer.truss !== null && phytomer.truss !== undefined) {
      const truss = fields(phytomer.truss, "a truss");
      let bearing = false;
      const flowers = list(truss, "flowers").map((flowerValue) => {
        const flower = fields(flowerValue, "a flower");
        const fruits = flower.fruit === null || flower.fruit === undefined ? [] : [flower.fruit];
        const children = fruits.map((value) => {
          const fruit = fields(value, "a fruit");
          const drawn = DRAWN_FRUIT_STAGES.has(fruit.stage);
          bearing ||= drawn;
          return node(fruit, text(fruit, "fruit_id"), "fruit", drawn);
        });
        const drawn = DRAWN_FLOWER_STAGES.has(flower.stage);
        bearing ||= drawn;
        return node(flower, text(flower, "flower_id"), "flower", drawn, children);
      });
      // A truss that bears nothing more has been cut, or is about to be.
      children.push(node(truss, text(truss, "truss_id"), "truss", bearing, flowers));
    }
    return node(phytomer, text(phytomer, "phytomer_id"), "phytomer", false, children);
  });
  const stemNode = node(stem, text(stem, "axis_id"), "stem", false, phytomers);
  return node(plant, text(plant, "plant_id"), "plant", false, [stemNode]);
}

/** Everything done to the plant, or asked of it, in order. */
export function plantHistory(body: unknown): PlantEvent[] {
  const plant = fields(body, "the plant");
  const history = plant.history === undefined ? [] : list(plant, "history");
  return history.map((value) => {
    const event = fields(value, "an event");
    if (typeof event.applied !== "boolean") {
      throw new Error("applied is not true or false");
    }
    return {
      thermalTime: number(event, "thermal_time"),
      applied: event.applied,
      note: text(event, "note"),
    };
  });
}

/** Which of the plant lab's plants, on which run of the lab. */
export interface LabPlant extends LabRun {
  plantId: string;
}

/** Asks the plant lab for one of its plant's structure on a run, as
 * `labRunQuery` writes it; any failure becomes `unavailable`. */
export async function loadPlantStructure(
  plantId: string,
  runQuery: string,
  fetchFn: typeof fetch = fetch,
): Promise<StructureState> {
  try {
    const query = `${runQuery}&plant=${encodeURIComponent(plantId)}`;
    const response = await fetchFn(`${PLANT_LAB_STRUCTURE_URL}?${query}`);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    const body: unknown = await response.json();
    return { status: "loaded", tree: organTree(body), history: plantHistory(body) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}
