import { Fold } from "./design/Fold";
import type { Fold as FoldState } from "./folds";
import { capitalised, describeGroups, inGroups } from "./groups";
import { formatValue, onAndRest, setBeside } from "./readouts";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { PERCENT } from "./units";

// The sliders move in steps of 5%.
const STEP_PERCENT = 5;

interface OpeningState {
  openingId: string;
  label: string;
  /** What it is, `roof_vent`, by which it is listed with others of its kind. */
  kind: string;
  fraction: number;
  apertureM2: number;
}

/** The doors and vents a scene holds, with how far each stands open. */
export function openingsIn(snapshot: SceneSnapshot): OpeningState[] {
  return snapshot.entities.flatMap((entity) => {
    const { opening_id, open_fraction, aperture_m2, opening_kind } = entity.properties;
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
        kind: typeof opening_kind === "string" ? opening_kind : opening_id,
        fraction: open_fraction,
        apertureM2: aperture_m2,
      },
    ];
  });
}

/** The doors and vents in a line, as the scene drawn has them, by kind (P22.8):
 * `Openings: roof vents 100%; door shut`; a kind whose pieces stand apart, by
 * piece: `roof vent 1 100%; roof vent 2, door shut`. */
export function describeOpenings(openings: readonly OpeningState[]): string {
  const { running, idle } = describeGroups(
    inGroups(openings.map((opening) => ({ ...opening, level: opening.fraction }))),
  );
  return `Openings: ${onAndRest(running, idle, "shut")}`;
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
  notDrawn = {},
  fold,
  onChange,
}: {
  snapshot: SceneSnapshot;
  /** The fractions asked for, which a slider shows until the scene catches up. */
  requested: Readonly<Record<string, number>>;
  /** Those of them no scene will catch up with, as in a stored run: the reading,
   * still of the scene, says them beside it. */
  notDrawn?: Readonly<Record<string, number>> | undefined;
  fold: FoldState;
  onChange: (openings: Record<string, number>) => void;
}) {
  const openings = openingsIn(snapshot);
  if (openings.length === 0) {
    return null;
  }
  return (
    <Fold
      className="openings-fold"
      open={fold.open}
      onToggle={fold.onToggle}
      summary={<span data-testid="openings-summary">{describeOpenings(openings)}</span>}
    >
      <fieldset className="opening-controls" aria-label="Openings">
        {inGroups(openings.map((opening) => ({ ...opening, level: opening.fraction }))).flatMap(
          (group) => [
            ...(group.pieces.length > 1
              ? [
                  <p key={`${group.name}-name`} className="opening-group">
                    {capitalised(group.name)}
                  </p>,
                ]
              : []),
            ...group.pieces.map(({ piece: { openingId, label, fraction, apertureM2 }, name }) => {
              const shown = requested[openingId] ?? fraction;
              return (
                <label key={openingId} className="opening-control">
                  <span>{name}</span>
                  <input
                    type="range"
                    aria-label={label}
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
                    {setBeside(notDrawn[openingId], fraction)}
                  </span>
                </label>
              );
            }),
          ],
        )}
      </fieldset>
    </Fold>
  );
}
