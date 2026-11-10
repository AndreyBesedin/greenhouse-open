import { useEffect, useState } from "react";

/** The sides of the view whose panels fold to a stripe at their inner edge
 * (#304): the info panel's, at the left, and the View panel's, at the
 * right. */
export type PanelSide = "info" | "view";

/** What folds to a stripe: a side's panels, or a replay's controls under the
 * view (P22.9). */
export type Foldable = PanelSide | "transport";

// Where what is folded is kept, in this browser, as the panels' theme is: a
// person's own, never the address's.
const STORED_AS = "greenhouse-sim.folded";
const FOLDABLE: readonly Foldable[] = ["info", "view", "transport"];
const SIDES: readonly PanelSide[] = ["info", "view"];
const TRANSPORT: readonly "transport"[] = ["transport"];

/** What was folded when this browser last showed it, none if it cannot say. */
export function storedFolds(): ReadonlySet<Foldable> {
  try {
    const stored = (localStorage.getItem(STORED_AS) ?? "").split(",");
    return new Set(FOLDABLE.filter((each) => stored.includes(each)));
  } catch {
    return new Set();
  }
}

/** Which of `own` are folded, kept for the next visit beside what others keep
 * under the same key: the viewer's sides and a replay's controls are each a
 * page's own, one inside the other. */
function useFolds<F extends Foldable>(
  own: readonly F[],
): [ReadonlySet<F>, (each: F) => void, (each: F) => void] {
  const [folded, setFolded] = useState(
    () => new Set(own.filter((each) => storedFolds().has(each))) as ReadonlySet<F>,
  );
  useEffect(() => {
    try {
      const others = [...storedFolds()].filter(
        (each) => !(own as readonly Foldable[]).includes(each),
      );
      localStorage.setItem(STORED_AS, [...others, ...folded].sort().join(","));
    } catch {
      // Kept for this visit only: a private window may keep nothing.
    }
  }, [own, folded]);
  function toggle(each: F): void {
    setFolded((was) => {
      const next = new Set(was);
      if (!next.delete(each)) {
        next.add(each);
      }
      return next;
    });
  }
  function unfold(each: F): void {
    setFolded((was) => {
      if (!was.has(each)) {
        return was;
      }
      const next = new Set(was);
      next.delete(each);
      return next;
    });
  }
  return [folded, toggle, unfold];
}

/** Which sides' panels are folded, kept for the next visit; a fold or unfold
 * of one, and an unfold of one, if it is folded. */
export function usePanelFolds(): [
  ReadonlySet<PanelSide>,
  (side: PanelSide) => void,
  (side: PanelSide) => void,
] {
  return useFolds(SIDES);
}

/** Whether a replay's controls under the view are folded, kept for the next
 * visit as the sides are; and a fold or unfold of them. */
export function useTransportFold(): [boolean, () => void] {
  const [folded, toggle] = useFolds(TRANSPORT);
  return [folded.has("transport"), () => toggle("transport")];
}
