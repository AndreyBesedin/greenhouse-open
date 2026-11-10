import type { Foldable } from "./panelFolds";

// What each stripe folds, and the arrow pointing the way a press moves what it
// folds: towards the screen's edge while it is open, back over the view once
// folded.
const STRIPES: Record<Foldable, { panels: string; fold: string; open: string }> = {
  info: { panels: "the info panel", fold: "◀", open: "▶" },
  view: { panels: "the View panel", fold: "▶", open: "◀" },
  transport: { panels: "the controls under the view", fold: "▼", open: "▲" },
};

/**
 * The narrow stripe along what it folds, in a colour of its own, with an arrow
 * on it (#304): a side's panels, the whole height of their inner edge, or a
 * replay's controls under the view, the whole width of their upper edge (P22.9).
 * Pressed, it folds them down to the stripe alone, at the screen's edge, its
 * arrow turned the other way, and pressed again, it opens them as they were. A
 * docked, narrow window shows no side's stripe (styles.css).
 */
export function PanelStripe({
  side,
  folded,
  onToggle,
}: {
  side: Foldable;
  folded: boolean;
  onToggle: () => void;
}) {
  const { panels, fold, open } = STRIPES[side];
  return (
    <button
      type="button"
      className={side === "transport" ? "panel-stripe panel-stripe-across" : "panel-stripe"}
      data-testid={`${side}-stripe`}
      aria-expanded={!folded}
      aria-label={folded ? `Open ${panels}` : `Fold ${panels}`}
      title={folded ? `Open ${panels}` : `Fold ${panels}`}
      onClick={onToggle}
    >
      <span aria-hidden="true">{folded ? open : fold}</span>
    </button>
  );
}
