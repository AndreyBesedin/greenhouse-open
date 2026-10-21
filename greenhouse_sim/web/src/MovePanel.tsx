import { type Offset, SNAP_DECIMALS, SNAP_M } from "./scene/moves";

/** A distance moved along an axis, signed, to the snap. */
function along(metres: number, axis: string): string {
  const shown = Math.abs(metres) < SNAP_M / 2 ? 0 : metres;
  const sign = shown > 0 ? "+" : shown < 0 ? "−" : "";
  return `${sign}${Math.abs(shown).toFixed(SNAP_DECIMALS)} m along ${axis}`;
}

/** An item that stands moved: what it is, what it is called, and how far it
 * stands from where its layout places it. */
export interface StandingMove {
  item: string;
  label: string;
  by: Offset;
}

/** A Move session under way (#271): every item that stands moved in the
 * layout it makes, whether that differs from the run drawn, whether the
 * view follows the run played back, which it then starts over, whether it
 * is being applied, and why it could not be, if it could not. */
export interface MoveDraft {
  moves: readonly StandingMove[];
  changed: boolean;
  following: boolean;
  applying: boolean;
  failure: string | null;
}

/**
 * Moving equipment and sensors across the floor (#209, #271). "Move" starts
 * a session: each item selected and dragged in the view moves, in 10 cm
 * steps, inside the house, and stays where it is dropped, drawn there, while
 * nothing is asked of the simulator. The session lists the moves, each to be
 * put back, and says what applying them does: moving equipment changes the
 * house's climate, so they make a new run, from its first day. "Start a new
 * run with these moves" applies them all at once; "Cancel", or Escape,
 * leaves everything as it was.
 */
export function MovePanel({
  item,
  draft,
  onMove,
  onPutBack,
  onPutEverythingBack,
  onApply,
  onCancel,
}: {
  /** The selected item, if it can be moved: what it is called, and how far
   * it stands from where its layout places it, the session's moves and a
   * drag under way included, or null where its layout places it. */
  item: { label: string; movedBy: Offset | null } | null;
  /** The session under way, if one is. */
  draft: MoveDraft | null;
  onMove: () => void;
  onPutBack: (item: string) => void;
  onPutEverythingBack: () => void;
  onApply: () => void;
  onCancel: () => void;
}) {
  return (
    <section className="move-panel" aria-label="Move">
      {item !== null && (
        <p data-testid="move-offset">
          {item.movedBy === null
            ? `The ${item.label} stands where its layout places it.`
            : `The ${item.label} stands ${along(item.movedBy.dx, "x")} and ${along(item.movedBy.dy, "y")} from where its layout places it.`}
        </p>
      )}
      {draft === null ? (
        <div className="move-actions">
          <button type="button" onClick={onMove}>
            Move
          </button>
        </div>
      ) : (
        <Session
          draft={draft}
          onPutBack={onPutBack}
          onPutEverythingBack={onPutEverythingBack}
          onApply={onApply}
          onCancel={onCancel}
        />
      )}
    </section>
  );
}

function Session({
  draft,
  onPutBack,
  onPutEverythingBack,
  onApply,
  onCancel,
}: {
  draft: MoveDraft;
  onPutBack: (item: string) => void;
  onPutEverythingBack: () => void;
  onApply: () => void;
  onCancel: () => void;
}) {
  const { moves, changed, following, applying, failure } = draft;
  return (
    <>
      <p data-testid="move-new-run">
        Moving equipment changes the house's climate, so it is a new run: applying these moves
        starts it from its first day.
        {following && " The run played back starts over with them, and the view follows it."}
      </p>
      <p className="move-hint">
        Select equipment or a sensor and drag in the view: it moves as far as the pointer does,
        along the floor, in 10 cm steps, and stays inside the house. Escape cancels a drag, or the
        moves.
      </p>
      {moves.length === 0 ? (
        <p data-testid="move-list">Everything stands where its layout places it.</p>
      ) : (
        <ul className="move-list" data-testid="move-list" aria-label="Moves">
          {moves.map(({ item, label, by }) => (
            <li key={item}>
              {label}: {along(by.dx, "x")} and {along(by.dy, "y")}{" "}
              <button
                type="button"
                aria-label={`Put the ${label} back`}
                disabled={applying}
                onClick={() => onPutBack(item)}
              >
                Put back
              </button>
            </li>
          ))}
        </ul>
      )}
      {failure !== null && (
        <p role="alert" data-testid="move-failure">
          The run played back could not start over: {failure}.
        </p>
      )}
      <div className="move-actions">
        <button type="button" disabled={!changed || applying} onClick={onApply}>
          {applying ? "Starting the new run…" : "Start a new run with these moves"}
        </button>
        <button
          type="button"
          disabled={moves.length === 0 || applying}
          onClick={onPutEverythingBack}
        >
          Put everything back
        </button>
        <button type="button" disabled={applying} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </>
  );
}
