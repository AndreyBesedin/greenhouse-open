/**
 * A draft's edits, each undone and redone in one step (P12.2): what was
 * before the one shown, it, and what an undo left to redo, which a new edit
 * forgets.
 */

/** How many edits back an undo reaches. */
export const MOST_UNDOS = 100;

export interface History<T> {
  past: readonly T[];
  present: T;
  future: readonly T[];
}

/** A history that begins at `present`, with nothing to undo or redo. */
export function begun<T>(present: T): History<T> {
  return { past: [], present, future: [] };
}

/** `history` with `next` shown, the edit before it the last to undo. */
export function edited<T>(history: History<T>, next: T): History<T> {
  return {
    past: [...history.past, history.present].slice(-MOST_UNDOS),
    present: next,
    future: [],
  };
}

/** `history` one edit back, if it has one. */
export function undone<T>(history: History<T>): History<T> {
  const previous = history.past.at(-1);
  if (previous === undefined) {
    return history;
  }
  return {
    past: history.past.slice(0, -1),
    present: previous,
    future: [history.present, ...history.future],
  };
}

/** `history` one undone edit on, if it has one. */
export function redone<T>(history: History<T>): History<T> {
  const [next, ...rest] = history.future;
  if (next === undefined) {
    return history;
  }
  return { past: [...history.past, history.present], present: next, future: rest };
}
