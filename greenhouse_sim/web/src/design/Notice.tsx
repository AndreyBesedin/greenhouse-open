import type { ReactNode } from "react";

/** A `problem` is said at once, interrupting; a `status` when the reader pauses. */
export type NoticeKind = "problem" | "status";

export interface NoticeProps {
  kind: NoticeKind;
  /** What it says: a notice is never a colour alone. */
  children: ReactNode;
  /** The class a page places it by. */
  className?: string | undefined;
}

/** A line a page tells as it changes, its role set by its kind. */
export function Notice({ kind, children, className }: NoticeProps) {
  const kindOf = `ds-notice ds-notice-${kind}`;
  return (
    <p
      role={kind === "problem" ? "alert" : "status"}
      className={className === undefined ? kindOf : `${kindOf} ${className}`}
    >
      {children}
    </p>
  );
}
