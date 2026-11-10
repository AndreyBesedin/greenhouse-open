import type { ComponentProps, ReactNode } from "react";

/** A `problem` is said at once, interrupting; a `status` when the reader pauses. */
export type NoticeKind = "problem" | "status";

export type NoticeProps = Omit<ComponentProps<"p">, "role" | "children"> & {
  kind: NoticeKind;
  /** What it says: a notice is never a colour alone. */
  children: ReactNode;
};

/** A line a page tells as it changes, its role set by its kind; a problem is drawn
 * in `--warn`. A page places it by a `className` of its own, and a test finds it by
 * its `data-testid`. */
export function Notice({ kind, className, ...rest }: NoticeProps) {
  const kindOf = `ds-notice ds-notice-${kind}`;
  return (
    <p
      role={kind === "problem" ? "alert" : "status"}
      className={className === undefined ? kindOf : `${kindOf} ${className}`}
      {...rest}
    />
  );
}
