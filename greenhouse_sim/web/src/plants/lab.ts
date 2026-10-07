import type { CameraPose } from "../camera";

// The plant lab opens on its row, which runs along +y from its first plant at
// the world's origin, its plants growing from about 20 cm on day 0 to about
// two metres by its last day: from in front and to the left of the first
// plant, looking along the row, so that the nearest plants stand right of the
// middle, clear of the info panel, and whole on the last day, and the row
// recedes towards the panel.
export const PLANT_LAB_POSE: CameraPose = {
  position: { x: -1.7, y: -2.4, z: 1.7 },
  target: { x: 0.6, y: 2.5, z: 0.9 },
};

// The plant lab's run, from its transplant on day 0 to this day, the seed it
// first draws its row from, and the plant whose structure it shows first, as
// the simulator's lab has them (`services/plants.py`).
export const PLANT_LAB_LAST_DAY = 90;
export const PLANT_LAB_SEED = 1;
export const PLANT_LAB_FIRST_PLANT = "p01";
// The environment the lab keeps its plants in unless asked for another.
export const PLANT_LAB_REFERENCE = "reference";

/** An action a run asks of one of its plants at the start of a day: its kind
 * and the organ it acts on, or for lowering the stem, by how many internodes. */
export interface LabAction {
  day: number;
  plantId: string;
  kind: "remove_leaf" | "harvest_fruit" | "harvest_truss" | "lower_stem";
  target: string;
}

const ACTION_KINDS: ReadonlySet<string> = new Set<LabAction["kind"]>([
  "remove_leaf",
  "harvest_fruit",
  "harvest_truss",
  "lower_stem",
]);
// A scheduled action is written `day:plant:action:organ`.
const ACTION_PARTS = 4;

/** A run of the plant lab: the day shown, the seed its row is drawn from, the
 * environment its plants live in and, if `versus` names another, the one
 * every second plant lives in instead; and the actions it schedules. */
export interface LabRun {
  day: number;
  seed: number;
  environment: string;
  versus: string | null;
  actions: readonly LabAction[];
}

export const FIRST_LAB_RUN: LabRun = {
  day: 0,
  seed: PLANT_LAB_SEED,
  environment: PLANT_LAB_REFERENCE,
  versus: null,
  actions: [],
};

/** An action as the address bar and the simulator's lab write it. */
export function actionText(action: LabAction): string {
  return `${action.day}:${action.plantId}:${action.kind}:${action.target}`;
}

/** An action from its text, or null if the text is not one. */
export function actionFrom(text: string): LabAction | null {
  const parts = text.split(":");
  const [day, plantId, kind, target] = parts;
  if (
    parts.length !== ACTION_PARTS ||
    day === undefined ||
    !/^\d+$/.test(day) ||
    plantId === undefined ||
    kind === undefined ||
    !ACTION_KINDS.has(kind) ||
    target === undefined
  ) {
    return null;
  }
  return { day: Number(day), plantId, kind: kind as LabAction["kind"], target };
}

/** A run's actions as query parameters, in the order they are asked. */
export function actionsQuery(actions: readonly LabAction[]): string[] {
  return actions.map((action) => `act=${encodeURIComponent(actionText(action))}`);
}

/** A run as the simulator's lab is asked for it. */
export function labRunQuery(run: LabRun): string {
  const parts = [
    `day=${run.day}`,
    `seed=${run.seed}`,
    `environment=${encodeURIComponent(run.environment)}`,
    ...(run.versus === null ? [] : [`versus=${encodeURIComponent(run.versus)}`]),
    ...actionsQuery(run.actions),
  ];
  return parts.join("&");
}
