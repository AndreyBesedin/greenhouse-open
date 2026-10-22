import { type KeyboardEvent, useEffect, useRef, useState } from "react";

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
 * nothing is asked of the simulator. The session says in a line what
 * applying the moves does, the rest folded under it, and lists the moves,
 * each to be put back. Moving equipment changes the house's climate, so the
 * moves make a new run from its first day, which keeps the run's target
 * changes (decision 0049). "Start a new run with these moves" asks first,
 * then applies them all at once (#305); "Cancel", or Escape, leaves
 * everything as it was.
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

/** Its moves' new run, said in a line before anything is moved. */
function newRun(following: boolean): string {
  return following
    ? "Drag equipment or a sensor in the view to move it. Applying the moves starts the run played back again from its first day, and the view follows it."
    : "Drag equipment or a sensor in the view to move it. Applying the moves starts the run again from its first day.";
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
  // Applying asks first, in the panel: the run starts again from its first
  // day, which no Back of the view's own undoes for the run played back.
  const [confirming, setConfirming] = useState(false);
  const asking = confirming && !applying;
  useEffect(() => {
    if (applying) {
      setConfirming(false);
    }
  }, [applying]);
  const confirm = useRef<HTMLButtonElement>(null);
  const apply = useRef<HTMLButtonElement>(null);
  const asked = useRef(false);
  useEffect(() => {
    if (asking) {
      confirm.current?.focus();
    } else if (asked.current) {
      apply.current?.focus();
    }
    asked.current = asking;
  }, [asking]);
  // Escape in the question goes back to the moves, rather than cancel them.
  function backOnEscape(event: KeyboardEvent<HTMLButtonElement>): void {
    if (event.key === "Escape") {
      event.preventDefault();
      setConfirming(false);
    }
  }
  return (
    <>
      <p data-testid="move-new-run">{newRun(following)}</p>
      <details className="move-details">
        <summary>How moving works</summary>
        <p className="move-hint">
          Moving equipment changes the house's climate, so the moves make a new run, which keeps the
          heating targets changed in the run. An item moves as far as the pointer does, along the
          floor, in 10 cm steps, and stays inside the house. Escape cancels a drag, or the moves.
        </p>
      </details>
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
      {asking ? (
        <fieldset className="move-confirm" aria-describedby="move-confirm-question">
          <legend>Start a new run?</legend>
          <p id="move-confirm-question" data-testid="move-confirm">
            {following ? "The run played back" : "The run"} starts again from its first day with
            these moves; the moment reached is left behind.
          </p>
          <div className="move-actions">
            <button
              ref={confirm}
              type="button"
              disabled={!changed}
              onKeyDown={backOnEscape}
              onClick={() => {
                setConfirming(false);
                onApply();
              }}
            >
              Start the new run
            </button>
            <button type="button" onKeyDown={backOnEscape} onClick={() => setConfirming(false)}>
              Back to the moves
            </button>
          </div>
        </fieldset>
      ) : (
        <div className="move-actions">
          <button
            ref={apply}
            type="button"
            disabled={!changed || applying}
            onClick={() => setConfirming(true)}
          >
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
      )}
    </>
  );
}
