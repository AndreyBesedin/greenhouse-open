import type { PanelSide } from "./panelFolds";

// What each side's stripe folds, and the arrow pointing the way a press
// moves the panels: towards the screen's edge while they are open, back
// over the view once folded.
const SIDES: Record<PanelSide, { panels: string; fold: string; open: string }> = {
  info: { panels: "the info panel", fold: "◀", open: "▶" },
  view: { panels: "the View panel", fold: "▶", open: "◀" },
};

/**
 * The narrow stripe along a side's panels' inner edge, in a colour of its
 * own, with an arrow on it (#304): pressed, it folds the panels down to the
 * stripe alone, at the screen's edge, its arrow turned the other way, and
 * pressed again, it opens them as they were. A docked, narrow window shows
 * none (styles.css).
 */
export function PanelStripe({
  side,
  folded,
  onToggle,
}: {
  side: PanelSide;
  folded: boolean;
  onToggle: () => void;
}) {
  const { panels, fold, open } = SIDES[side];
  return (
    <button
      type="button"
      className="panel-stripe"
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
