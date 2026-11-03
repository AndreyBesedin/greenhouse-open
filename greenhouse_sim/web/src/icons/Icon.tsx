import type { ReactNode } from "react";

/** The size, in pixels, an icon is drawn at unless it says another. */
export const ICON_SIZE_PX = 18;

interface IconProps {
  /** The icon's drawing, in the box of `viewBox`. */
  children: ReactNode;
  viewBox: string;
  /** Drawn as outlines in the text's colour, or filled in it. */
  style: "outline" | "filled";
  size?: number;
}

/**
 * What every icon of the viewer is drawn in: in the colour of the text beside
 * it, so that it follows the light and dark themes, and hidden from assistive
 * technology, since an icon is decoration and its button or link is named by
 * its words. An icon that stands alone, with no words, is not made with this.
 */
export function Icon({ children, viewBox, style, size = ICON_SIZE_PX }: IconProps) {
  const drawn =
    style === "outline"
      ? {
          fill: "none",
          stroke: "currentColor",
          strokeWidth: 2,
          strokeLinecap: "round" as const,
          strokeLinejoin: "round" as const,
        }
      : { fill: "currentColor" };
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox={viewBox}
      aria-hidden="true"
      focusable="false"
      {...drawn}
    >
      {children}
    </svg>
  );
}
