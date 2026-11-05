import type { ReactElement } from "react";

import { Button, type ButtonProps } from "./Button";

export type IconButtonProps = Omit<ButtonProps, "aria-label" | "aria-labelledby" | "children"> & {
  /** Its name, which is all a person who cannot see the icon is told of it. */
  label: string;
  /** An icon of `src/icons/`, which stays decoration. */
  children: ReactElement;
};

/**
 * A button with an icon and no words: its `label` names it. The types cannot refuse
 * the hyphenated attributes that would name it otherwise, so they are set here, last:
 * `aria-labelledby` would win over `aria-label`.
 */
export function IconButton({ label, className, ...rest }: IconButtonProps) {
  return (
    <Button
      {...rest}
      className={className === undefined ? "ds-icon-button" : `ds-icon-button ${className}`}
      aria-label={label}
      aria-labelledby={undefined}
    />
  );
}
