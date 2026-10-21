// Generated from greenhouse_sim/biology/tomato/organ/plant.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * Where a leaf is in its life.
 */
export type LeafStage = "expanding" | "mature" | "removed";
export type FlowerStage = "bud" | "open" | "set" | "aborted";
/**
 * Where a fruit is in its life, from set to picked.
 */
export type FruitStage = "attached" | "aborted" | "harvested";
export type PlantAction = RemoveLeaf | HarvestFruit | HarvestTruss | LowerStem;

/**
 * One plant, organ by organ, and the thermal time it has accumulated.
 */
export interface Plant {
  born_tt: number;
  plant_id: string;
  thermal_time: number;
  stem: Axis;
  seed: number;
  traits: PlantTraits;
  laid_internodes: number;
  history: PlantEvent[];
}
export interface Axis {
  born_tt: number;
  axis_id: string;
  phytomers: Phytomer[];
}
export interface Phytomer {
  born_tt: number;
  phytomer_id: string;
  rank: number;
  internode: Internode;
  leaf: Leaf;
  truss: Truss | null;
}
export interface Internode {
  born_tt: number;
  internode_id: string;
  length_cm: number;
  diameter_mm: number;
  final_length_cm: number;
  final_diameter_mm: number;
}
export interface Leaf {
  born_tt: number;
  leaf_id: string;
  length_cm: number;
  final_length_cm: number;
  stage: LeafStage;
}
export interface Truss {
  born_tt: number;
  truss_id: string;
  number: number;
  final_flower_count: number;
  flowers: Flower[];
}
export interface Flower {
  born_tt: number;
  flower_id: string;
  rank: number;
  stage: FlowerStage;
  fruit: Fruit | null;
}
export interface Fruit {
  born_tt: number;
  fruit_id: string;
  diameter_mm: number;
  final_diameter_mm: number;
  mass_g: number;
  breaker_tt: number;
  ripeness: number;
  stage: FruitStage;
}
/**
 * How one plant differs from its crop's typical plant: a factor on each
 * of the crop's values (1 for a typical plant), its turn about its stem,
 * and the latent vigour its factors share.
 */
export interface PlantTraits {
  vigour: number;
  phyllochron_scale: number;
  internode_length_scale: number;
  stem_diameter_scale: number;
  leaf_length_scale: number;
  leaf_insertion_scale: number;
  leaf_droop_scale: number;
  rotation_rad: number;
}
/**
 * An action done to a plant, or asked of it and refused.
 */
export interface PlantEvent {
  thermal_time: number;
  action: PlantAction;
  applied: boolean;
  note: string;
  organs: string[];
  harvested_g: number;
}
/**
 * Prune a leaf off the plant.
 */
export interface RemoveLeaf {
  kind: "remove_leaf";
  leaf_id: string;
}
/**
 * Pick one fruit.
 */
export interface HarvestFruit {
  kind: "harvest_fruit";
  fruit_id: string;
}
/**
 * Cut a truss: pick its fruits, and drop the flowers it still bears.
 */
export interface HarvestTruss {
  kind: "harvest_truss";
  truss_id: string;
}
/**
 * Lower the stem, laying its lowest standing internodes down along the
 * row; they must be bare, their leaves removed and their trusses cut.
 */
export interface LowerStem {
  kind: "lower_stem";
  internodes: number;
}
