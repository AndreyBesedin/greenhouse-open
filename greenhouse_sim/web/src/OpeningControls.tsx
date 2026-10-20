import type { Fold } from "./folds";
import { formatValue, onAndRest } from "./readouts";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { PERCENT } from "./units";

// The sliders move in steps of 5%.
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

/** The doors and vents in a line, as the scene drawn has them: `Openings:
 * roof vent 1 100%; roof vent 2, door shut`. */
export function describeOpenings(openings: readonly OpeningState[]): string {
  const open = openings
    .filter(({ fraction }) => fraction > 0)
    .map(({ label, fraction }) => `${label} ${Math.round(fraction * PERCENT)}%`);
  const shut = openings.filter(({ fraction }) => fraction === 0).map(({ label }) => label);
  return `Openings: ${onAndRest(open, shut, "shut")}`;
}

/**
 * A slider per door and vent, folded to a line that says how far each
 * stands open (#206). Moving one asks the simulator for the scene
 * with that opening set, so the geometry stays the simulator's; the scene
 * shown says how far each stands open, and the aperture it exposes.
 */
export function OpeningControls({
  snapshot,
  requested,
  fold,
  onChange,
}: {
  snapshot: SceneSnapshot;
  /** The fractions asked for, which a slider shows until the scene catches up. */
  requested: Readonly<Record<string, number>>;
  fold: Fold;
  onChange: (openings: Record<string, number>) => void;
}) {
  const openings = openingsIn(snapshot);
  if (openings.length === 0) {
    return null;
  }
  return (
    <details className="openings-fold" open={fold.open} onToggle={fold.onToggle}>
      <summary data-testid="openings-summary">{describeOpenings(openings)}</summary>
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
    </details>
  );
}
