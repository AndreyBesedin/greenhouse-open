import { type Offset, SNAP_DECIMALS, SNAP_M } from "./scene/moves";

/** A distance moved along an axis, signed, to the snap. */
function along(metres: number, axis: string): string {
  const shown = Math.abs(metres) < SNAP_M / 2 ? 0 : metres;
  const sign = shown > 0 ? "+" : shown < 0 ? "−" : "";
  return `${sign}${Math.abs(shown).toFixed(SNAP_DECIMALS)} m along ${axis}`;
}

/**
 * Moving the selected piece of equipment or sensor across the floor (#209):
 * "Move" starts it, and while it lasts a drag in the view moves the item, in
 * 10 cm steps, inside the house; each move made is another layout, run
 * afresh. "Undo move" takes back the latest, as Back does, and "Put back"
 * returns the item to where its layout places it.
 */
export function MovePanel({
  label,
  moving,
  movedBy,
  canUndo,
  onMoving,
  onUndo,
  onPutBack,
}: {
  /** What the item is called. */
  label: string;
  /** Whether it is being moved. */
  moving: boolean;
  /** How far it stands from where its layout places it, a drag under way
   * included, or null where its layout places it. */
  movedBy: Offset | null;
  /** Whether the latest move made can be taken back. */
  canUndo: boolean;
  onMoving: (moving: boolean) => void;
  onUndo: () => void;
  onPutBack: () => void;
}) {
  return (
    <section className="move-panel" aria-label="Move">
      <p data-testid="move-offset">
        {movedBy === null
          ? `The ${label} stands where its layout places it.`
          : `The ${label} stands ${along(movedBy.dx, "x")} and ${along(movedBy.dy, "y")} from where its layout places it.`}
      </p>
      {moving && (
        <p className="move-hint">
          Drag in the view: the {label} moves as far as the pointer does, along the floor, in 10 cm
          steps, and stays inside the house. Escape cancels a drag, or stops moving.
        </p>
      )}
      <div className="move-actions">
        <button type="button" aria-pressed={moving} onClick={() => onMoving(!moving)}>
          {moving ? "Done moving" : "Move"}
        </button>
        <button type="button" disabled={!canUndo} onClick={onUndo}>
          Undo move
        </button>
        <button type="button" disabled={movedBy === null} onClick={onPutBack}>
          Put back
        </button>
      </div>
    </section>
  );
}
