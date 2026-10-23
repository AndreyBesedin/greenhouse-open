import { type ReactNode, useLayoutEffect, useRef } from "react";
import { PanelStripe } from "./PanelStripe";
import type { PanelSide as Side } from "./panelFolds";

/**
 * A side's column of panels beside the stripe along its inner edge that
 * folds it (#304): the info panel's, at the left, its stripe after it, and
 * the View panel's, at the right, its stripe before it.
 *
 * Folded, the column leaves the layout, and an overflowing panel in it no
 * longer has anything to scroll, so the browser puts it back at its top:
 * where each scrolled one stood is kept as the side folds, and given back
 * as it opens, by its stripe or otherwise.
 */
export function PanelSide({
  side,
  folded,
  onToggle,
  children,
}: {
  side: Side;
  folded: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  const column = useRef<HTMLDivElement>(null);
  const scrolled = useRef(new Map<Element, number>());
  function toggle(): void {
    const panels = column.current;
    if (!folded && panels !== null) {
      scrolled.current = new Map(
        [panels, ...panels.querySelectorAll("*")]
          .filter((element) => element.scrollTop > 0)
          .map((element) => [element, element.scrollTop]),
      );
    }
    onToggle();
  }
  useLayoutEffect(() => {
    if (folded) {
      return;
    }
    for (const [element, top] of scrolled.current) {
      element.scrollTop = top;
    }
    scrolled.current = new Map();
  }, [folded]);

  const atTheEnd = side === "view";
  const stripe = <PanelStripe side={side} folded={folded} onToggle={toggle} />;
  return (
    <div
      className={["panel-side", atTheEnd ? "at-the-end" : "", folded ? "folded" : ""]
        .filter((name) => name !== "")
        .join(" ")}
    >
      {atTheEnd && stripe}
      <div ref={column} className={atTheEnd ? "panel-column at-the-end" : "panel-column"}>
        {children}
      </div>
      {!atTheEnd && stripe}
    </div>
  );
}
