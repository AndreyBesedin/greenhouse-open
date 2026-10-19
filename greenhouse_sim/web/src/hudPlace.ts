/** A box on the page, in CSS pixels, as `getBoundingClientRect` gives it. */
export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** How far a panel is moved from its place, in CSS pixels. */
export interface Offset {
  x: number;
  y: number;
}

/** A panel in its own place. */
export const UNMOVED: Offset = { x: 0, y: 0 };

/** Whether a panel is moved from its place. */
export function isMoved(offset: Offset): boolean {
  return offset.x !== 0 || offset.y !== 0;
}

/** Where `box`, drawn moved by `offset`, stands unmoved. */
export function unmoved(box: Box, offset: Offset): Box {
  return {
    left: box.left - offset.x,
    top: box.top - offset.y,
    right: box.right - offset.x,
    bottom: box.bottom - offset.y,
  };
}

/**
 * `wanted`, changed as little as it must be for a panel at `place`, when
 * unmoved, to stand within `bounds` once moved by it, so that a panel
 * dragged away can never be put out of reach. A panel taller or wider than
 * `bounds` keeps its top or its left edge within them, where its header is.
 */
export function within(wanted: Offset, place: Box, bounds: Box): Offset {
  return {
    x: between(wanted.x, bounds.left - place.left, bounds.right - place.right),
    y: between(wanted.y, bounds.top - place.top, bounds.bottom - place.bottom),
  };
}

/** `value` no lower than `low`, and no higher than `high` unless `high` is
 * lower than `low`, when `low` wins. */
function between(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(value, high));
}
