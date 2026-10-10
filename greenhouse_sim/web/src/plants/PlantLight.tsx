import { describePlantLight, type PlantsLightState } from "./light";

/** The sun's light on a plant, at the moment drawn and through the run's
 * first day, in a climate run's view. */
export function PlantLight({ plantId, state }: { plantId: string; state: PlantsLightState }) {
  if (state.status === "none") {
    return null;
  }
  if (state.status !== "loaded") {
    return (
      <p className="plant-light" data-testid="plant-light">
        {state.status === "loading"
          ? "Reading the plant's light…"
          : `The plant's light cannot be read: ${state.reason}.`}
      </p>
    );
  }
  const described = describePlantLight(state.light, plantId);
  if (described === null) {
    return null;
  }
  return (
    <dl className="plant-light" data-testid="plant-light" aria-label="Plant light">
      <dt>PAR now</dt>
      <dd data-testid="plant-par">{described.now}</dd>
      <dt>Day's light</dt>
      <dd data-testid="plant-daily-light">{described.day}</dd>
    </dl>
  );
}
