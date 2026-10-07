import { PLANT_LAB_LAST_DAY } from "./lab";

/**
 * The plant lab's day. Moving the slider asks the simulator for its plant on
 * that day, so its development stays the simulator's; the day shown is the
 * day of the scene on show, which the slider leads while the next arrives.
 */
export function PlantDay({
  day,
  shownDay,
  onDay,
}: {
  /** The day asked for. */
  day: number;
  /** The day of the scene on show, if one is. */
  shownDay: number | null;
  onDay: (day: number) => void;
}) {
  return (
    <fieldset className="lab-day" aria-label="Plant lab day">
      <label className="lab-day-control">
        <span>Day</span>
        <input
          type="range"
          min={0}
          max={PLANT_LAB_LAST_DAY}
          step={1}
          value={day}
          onChange={(event) => onDay(Number(event.target.value))}
        />
        <span data-testid="plant-day">{shownDay === null ? "…" : `day ${shownDay}`}</span>
      </label>
    </fieldset>
  );
}
