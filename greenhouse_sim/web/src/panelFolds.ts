import { useEffect, useState } from "react";

/** The sides of the view whose panels fold to a stripe at their inner edge
 * (#304): the info panel's, at the left, and the View panel's, at the
 * right. */
export type PanelSide = "info" | "view";

// Where the folded sides are kept, in this browser, as the panels' theme is:
// a person's own, never the address's.
const STORED_AS = "greenhouse-sim.folded";
const SIDES: readonly PanelSide[] = ["info", "view"];

/** The sides folded when this browser last showed the viewer, none if it
 * cannot say. */
export function storedFolds(): ReadonlySet<PanelSide> {
  try {
    const stored = (localStorage.getItem(STORED_AS) ?? "").split(",");
    return new Set(SIDES.filter((side) => stored.includes(side)));
  } catch {
    return new Set();
  }
}

/** Which sides' panels are folded, kept for the next visit; a fold or unfold
 * of one, and an unfold of one, if it is folded. */
export function usePanelFolds(): [
  ReadonlySet<PanelSide>,
  (side: PanelSide) => void,
  (side: PanelSide) => void,
] {
  const [folded, setFolded] = useState(storedFolds);
  useEffect(() => {
    try {
      localStorage.setItem(STORED_AS, [...folded].sort().join(","));
    } catch {
      // Kept for this visit only: a private window may keep nothing.
    }
  }, [folded]);
  function toggle(side: PanelSide): void {
    setFolded((was) => {
      const next = new Set(was);
      if (!next.delete(side)) {
        next.add(side);
      }
      return next;
    });
  }
  function unfold(side: PanelSide): void {
    setFolded((was) => {
      if (!was.has(side)) {
        return was;
      }
      const next = new Set(was);
      next.delete(side);
      return next;
    });
  }
  return [folded, toggle, unfold];
}
