import type { ComponentProps, ReactNode } from "react";

import { type ButtonLook, buttonClass } from "./buttonClass";

export type ButtonProps = ComponentProps<"button"> &
  ButtonLook & {
    /** Its words, which name it. */
    children: ReactNode;
  };

/**
 * A button: the browser's own element, so that a keyboard reaches it, Enter and
 * Space press it and `disabled` takes it out of both. It submits nothing unless
 * asked to, wherever it stands. A page places it by a `className` of its own.
 */
export function Button({ tone, size, className, type = "button", ...rest }: ButtonProps) {
  return <button type={type} className={buttonClass({ tone, size }, className)} {...rest} />;
}
