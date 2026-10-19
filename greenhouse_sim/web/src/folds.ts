import { type SyntheticEvent, useState } from "react";

/** Whether a panel folded to its line is open, and how it says it opened or
 * folded (#206). */
export interface Fold {
  open: boolean;
  onToggle: (event: SyntheticEvent<HTMLDetailsElement>) => void;
}

/** Panels' folds by name, each folded at first, and kept as they are while
 * the panels themselves come and go, as a day's scene loads. */
export function useFolds<Name extends string>(): (name: Name) => Fold {
  const [open, setOpen] = useState<ReadonlySet<Name>>(() => new Set());
  return (name) => ({
    open: open.has(name),
    onToggle: (event) => {
      const now = event.currentTarget.open;
      setOpen((current) => {
        if (current.has(name) === now) {
          return current;
        }
        const next = new Set(current);
        if (now) {
          next.add(name);
        } else {
          next.delete(name);
        }
        return next;
      });
    },
  });
}
