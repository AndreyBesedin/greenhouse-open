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

/** A run of the plant lab: the day shown, the seed its row is drawn from, the
 * environment its plants live in and, if `versus` names another, the one
 * every second plant lives in instead. */
export interface LabRun {
  day: number;
  seed: number;
  environment: string;
  versus: string | null;
}

export const FIRST_LAB_RUN: LabRun = {
  day: 0,
  seed: PLANT_LAB_SEED,
  environment: PLANT_LAB_REFERENCE,
  versus: null,
};

/** A run as the simulator's lab is asked for it. */
export function labRunQuery(run: LabRun): string {
  const parts = [
    `day=${run.day}`,
    `seed=${run.seed}`,
    `environment=${encodeURIComponent(run.environment)}`,
    ...(run.versus === null ? [] : [`versus=${encodeURIComponent(run.versus)}`]),
  ];
  return parts.join("&");
}
