import { type ReactNode, useLayoutEffect, useRef, useState } from "react";
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
 *
 * The stripe is as tall as the side's first panel, the info panel or the HUD,
 * however it grows or folds (P22.9): never shorter than its tab, and never over
 * the view below the panel, whose clicks are the scene's.
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
  const [panelPx, setPanelPx] = useState<number | null>(null);
  const foldedNow = useRef(folded);
  foldedNow.current = folded;
  useLayoutEffect(() => {
    const panel = column.current?.firstElementChild;
    if (panel === null || panel === undefined || typeof ResizeObserver === "undefined") {
      return;
    }
    // Folded, the panel leaves the column, unbounded by its height: the stripe keeps
    // the height it had open, and takes the panel's again as it opens.
    const observer = new ResizeObserver(() => {
      if (!foldedNow.current) {
        setPanelPx(panel.getBoundingClientRect().height);
      }
    });
    observer.observe(panel);
    return () => observer.disconnect();
  }, []);
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
  const stripe = <PanelStripe side={side} folded={folded} onToggle={toggle} heightPx={panelPx} />;
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
