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

export type StructureState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; tree: OrganNode };

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

/** An organ's thermal age, and its stage if it has one. */
function describe(organ: Fields, thermalTime: number): string {
  const age = `${Math.round(thermalTime - number(organ, "born_tt"))} °Cd`;
  const stage = organ.stage;
  return typeof stage === "string" ? `${age}, ${stage}` : age;
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
      node(leaf, text(leaf, "leaf_id"), "leaf", true),
    ];
    if (phytomer.truss !== null && phytomer.truss !== undefined) {
      const truss = fields(phytomer.truss, "a truss");
      const flowers = list(truss, "flowers").map((flowerValue) => {
        const flower = fields(flowerValue, "a flower");
        const fruit = flower.fruit;
        const fruits =
          fruit === null || fruit === undefined
            ? []
            : [
                node(
                  fields(fruit, "a fruit"),
                  text(fields(fruit, "a fruit"), "fruit_id"),
                  "fruit",
                  true,
                ),
              ];
        return node(flower, text(flower, "flower_id"), "flower", fruits.length === 0, fruits);
      });
      children.push(node(truss, text(truss, "truss_id"), "truss", true, flowers));
    }
    return node(phytomer, text(phytomer, "phytomer_id"), "phytomer", false, children);
  });
  const stemNode = node(stem, text(stem, "axis_id"), "stem", false, phytomers);
  return node(plant, text(plant, "plant_id"), "plant", false, [stemNode]);
}

/** Asks the plant lab for its plant's structure; any failure becomes
 * `unavailable`. */
export async function loadPlantStructure(fetchFn: typeof fetch = fetch): Promise<StructureState> {
  try {
    const response = await fetchFn(PLANT_LAB_STRUCTURE_URL);
    if (!response.ok) {
      return { status: "unavailable", reason: `the simulator API answered ${response.status}` };
    }
    return { status: "loaded", tree: organTree(await response.json()) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
}
