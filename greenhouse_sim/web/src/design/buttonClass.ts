/** What a button or a link drawn as one does: `primary` is what a page is for,
 * `danger` cannot be taken back, in red, and `go` sets a run going, in green. */
export type ButtonTone = "plain" | "primary" | "danger" | "go";
/** `target` is what a pointer or a finger is given to hit; `compact` is for dense
 * panels and forms. */
export type ButtonSize = "target" | "compact";

export interface ButtonLook {
  tone?: ButtonTone | undefined;
  size?: ButtonSize | undefined;
}

/** The classes of what is drawn as a button, and last the class a page places it by. */
export function buttonClass({ tone = "plain", size = "target" }: ButtonLook, placed = ""): string {
  return [
    "ds-button",
    tone === "plain" ? "" : `ds-button-${tone}`,
    size === "target" ? "" : `ds-button-${size}`,
    placed,
  ]
    .filter((name) => name !== "")
    .join(" ");
}
