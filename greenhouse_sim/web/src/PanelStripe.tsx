import type { Foldable } from "./panelFolds";

// The least a side's stripe stands, as a tab, beside a panel shorter than it.
const TAB_PX = 96;

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
 * on it (#304): a side's panels, along their inner edge as tall as the panel
 * beside it (`heightPx`), or a replay's controls under the view, the whole width
 * of their upper edge (P22.9).
 * Pressed, it folds them down to the stripe alone, at the screen's edge, its
 * arrow turned the other way, and pressed again, it opens them as they were. A
 * docked, narrow window shows no side's stripe (styles.css).
 */
export function PanelStripe({
  side,
  folded,
  onToggle,
  heightPx = null,
}: {
  side: Foldable;
  folded: boolean;
  onToggle: () => void;
  /** A side's panel's height, which its stripe takes, once measured. */
  heightPx?: number | null;
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
      style={heightPx === null ? undefined : { height: Math.max(TAB_PX, heightPx) }}
      onClick={onToggle}
    >
      <span aria-hidden="true">{folded ? open : fold}</span>
    </button>
  );
}
