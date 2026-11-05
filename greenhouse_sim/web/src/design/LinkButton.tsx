import type { ComponentProps, ReactNode } from "react";

import { type ButtonLook, buttonClass } from "./buttonClass";

export type LinkButtonProps = ComponentProps<"a"> &
  ButtonLook & {
    /** Where it goes: without one an `<a>` is no link, and no keyboard reaches it. */
    href: string;
    /** Its words, which name it. */
    children: ReactNode;
  };

/**
 * A link drawn as a button: it goes somewhere, and Enter follows it. It has no
 * `disabled`, as a link has none: where there is nowhere to go, a page shows no
 * link, or a `Button` that is disabled.
 */
export function LinkButton({ tone, size, className, children, ...rest }: LinkButtonProps) {
  return (
    <a className={buttonClass({ tone, size }, className)} {...rest}>
      {children}
    </a>
  );
}
