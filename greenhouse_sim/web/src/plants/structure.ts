import { contractReader, loadJson } from "../loadJson";
import { PERCENT } from "../units";
import { PLANT_SCHEMA } from "./generated/plantSchema";
import type { Plant } from "./generated/plantTypes";
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

/** A plant, checked rather than trusted. */
const readPlant = contractReader<Plant>(PLANT_SCHEMA, "the plant is not what the viewer expects");

// The stages in which the view draws a flower, and a fruit: a set flower is
// drawn as its fruit, and an aborted flower or fruit has dropped.
const DRAWN_FLOWER_STAGES: ReadonlySet<string> = new Set(["bud", "open"]);
const DRAWN_FRUIT_STAGES: ReadonlySet<string> = new Set(["attached"]);

/** What every organ has, and what some have: a stage, and a ripeness. */
interface Organ {
  born_tt: number;
  stage?: string;
  ripeness?: number;
}

/** An organ's thermal age, its stage if it has one, and how ripe it is if
 * it has started to ripen. */
function describe(organ: Organ, thermalTime: number): string {
  const age = `${Math.round(thermalTime - organ.born_tt)} °Cd`;
  const stage = organ.stage === undefined ? "" : `, ${organ.stage}`;
  const ripe =
    organ.ripeness !== undefined && organ.ripeness > 0
      ? `, ${Math.round(organ.ripeness * PERCENT)}% ripe`
      : "";
  return `${age}${stage}${ripe}`;
}

/** The plant's structure as a tree. */
export function organTree(plant: Plant): OrganNode {
  const thermalTime = plant.thermal_time;
  const node = (
    organ: Organ,
    id: string,
    kind: OrganNode["kind"],
    drawn: boolean,
    children: OrganNode[] = [],
  ): OrganNode => ({ id, kind, drawn, detail: describe(organ, thermalTime), children });

  const phytomers = plant.stem.phytomers.map((phytomer) => {
    const { internode, leaf, truss } = phytomer;
    const children = [
      node(internode, internode.internode_id, "internode", true),
      node(leaf, leaf.leaf_id, "leaf", leaf.stage !== "removed"),
    ];
    if (truss !== null) {
      let bearing = false;
      const flowers = truss.flowers.map((flower) => {
        const fruits = flower.fruit === null ? [] : [flower.fruit];
        const children = fruits.map((fruit) => {
          const drawn = DRAWN_FRUIT_STAGES.has(fruit.stage);
          bearing ||= drawn;
          return node(fruit, fruit.fruit_id, "fruit", drawn);
        });
        const drawn = DRAWN_FLOWER_STAGES.has(flower.stage);
        bearing ||= drawn;
        return node(flower, flower.flower_id, "flower", drawn, children);
      });
      // A truss that bears nothing more has been cut, or is about to be.
      children.push(node(truss, truss.truss_id, "truss", bearing, flowers));
    }
    return node(phytomer, phytomer.phytomer_id, "phytomer", false, children);
  });
  const stemNode = node(plant.stem, plant.stem.axis_id, "stem", false, phytomers);
  return node(plant, plant.plant_id, "plant", false, [stemNode]);
}

/** Everything done to the plant, or asked of it, in order. */
export function plantHistory(plant: Plant): PlantEvent[] {
  return plant.history.map((event) => ({
    thermalTime: event.thermal_time,
    applied: event.applied,
    note: event.note,
  }));
}

/** Which of the plant lab's plants, on which run of the lab. */
export interface LabPlant extends LabRun {
  plantId: string;
}

/** Asks the plant lab for one of its plant's structure on a run, as
 * `labRunQuery` writes it; any failure becomes `unavailable`. */
/** Where a plant's structure through a run of the lab is published. */
export function plantStructureUrl(plantId: string, runQuery: string): string {
  return `${PLANT_LAB_STRUCTURE_URL}?${runQuery}&plant=${encodeURIComponent(plantId)}`;
}

export async function loadPlantStructure(
  plantId: string,
  runQuery: string,
  fetchFn: typeof fetch = fetch,
): Promise<StructureState> {
  const answer = await loadJson(
    plantStructureUrl(plantId, runQuery),
    (body) => {
      const plant = readPlant(body);
      return { tree: organTree(plant), history: plantHistory(plant) };
    },
    fetchFn,
  );
  return answer.status === "loaded" ? { status: "loaded", ...answer.value } : answer;
}
