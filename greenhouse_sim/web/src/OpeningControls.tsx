import { formatValue } from "./readouts";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";

// The sliders move in steps of 5%.
const PERCENT = 100;
const STEP_PERCENT = 5;

interface OpeningState {
  openingId: string;
  label: string;
  fraction: number;
  apertureM2: number;
}

/** The doors and vents a scene holds, with how far each stands open. */
export function openingsIn(snapshot: SceneSnapshot): OpeningState[] {
  return snapshot.entities.flatMap((entity) => {
    const { opening_id, open_fraction, aperture_m2 } = entity.properties;
    if (
      typeof opening_id !== "string" ||
      typeof open_fraction !== "number" ||
      typeof aperture_m2 !== "number"
    ) {
      return [];
    }
    return [
      {
        openingId: opening_id,
        label: entity.label ?? opening_id,
        fraction: open_fraction,
        apertureM2: aperture_m2,
      },
    ];
  });
}

/**
 * A slider per door and vent. Moving one asks the simulator for the scene
 * with that opening set, so the geometry stays the simulator's; the scene
 * shown says how far each stands open, and the aperture it exposes.
 */
export function OpeningControls({
  snapshot,
  requested,
  onChange,
}: {
  snapshot: SceneSnapshot;
  /** The fractions asked for, which a slider shows until the scene catches up. */
  requested: Readonly<Record<string, number>>;
  onChange: (openings: Record<string, number>) => void;
}) {
  const openings = openingsIn(snapshot);
  if (openings.length === 0) {
    return null;
  }
  return (
    <fieldset className="opening-controls" aria-label="Openings">
      {openings.map(({ openingId, label, fraction, apertureM2 }) => {
        const shown = requested[openingId] ?? fraction;
        return (
          <label key={openingId} className="opening-control">
            <span>{label}</span>
            <input
              type="range"
              min={0}
              max={PERCENT}
              step={STEP_PERCENT}
              value={Math.round(shown * PERCENT)}
              onChange={(event) =>
                onChange({ ...requested, [openingId]: Number(event.target.value) / PERCENT })
              }
            />
            <span data-testid={`opening-${openingId}`}>
              {Math.round(fraction * PERCENT)}%, {formatValue(apertureM2)} m²
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
