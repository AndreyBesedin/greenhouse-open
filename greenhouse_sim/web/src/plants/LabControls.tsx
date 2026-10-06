import { PLANT_LAB_LAST_DAY } from "./lab";

/**
 * The plant lab's day and seed. Moving the slider asks the simulator for its
 * row on that day, so its development stays the simulator's; the day shown is
 * the day of the scene on show, which the slider leads while the next
 * arrives. Another seed draws another row of the same crop.
 */
export function LabControls({
  day,
  shownDay,
  seed,
  onDay,
  onSeed,
}: {
  /** The day asked for. */
  day: number;
  /** The day of the scene on show, if one is. */
  shownDay: number | null;
  seed: number;
  onDay: (day: number) => void;
  onSeed: (seed: number) => void;
}) {
  return (
    <fieldset className="lab-controls" aria-label="Plant lab">
      <label className="lab-control">
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
      <label className="lab-control">
        <span>Seed</span>
        <input
          type="number"
          min={0}
          step={1}
          value={seed}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (Number.isInteger(next) && next >= 0) {
              onSeed(next);
            }
          }}
        />
        <button type="button" onClick={() => onSeed(seed + 1)}>
          Another seed
        </button>
      </label>
    </fieldset>
  );
}
