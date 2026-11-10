import type { ReactNode } from "react";

import type { Fold as FoldState } from "../folds";

/** Its state, if a page keeps it: without, the browser's `<details>` keeps its own. */
export type FoldProps = Partial<FoldState> & {
  /** Its line, which shows folded or open, and opens or folds it. */
  summary: ReactNode;
  /** What it holds, shown when open. */
  children: ReactNode;
  /** The class a page places it by. */
  className?: string | undefined;
};

/** A section folded to its line: the browser's `<details>`, whose state `useFolds`
 * keeps, by its name, while the page around it is drawn again. */
export function Fold({ summary, children, className, open, onToggle }: FoldProps) {
  return (
    <details
      className={className === undefined ? "ds-fold" : `ds-fold ${className}`}
      open={open}
      onToggle={onToggle}
    >
      <summary>{summary}</summary>
      {children}
    </details>
  );
}
