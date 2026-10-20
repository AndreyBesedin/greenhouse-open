/**
 * What the viewer's small charts share (audit W12, `AUDIT.8`): their width,
 * in their `viewBox`'s units, how a value is placed up a chart, and their
 * points as an SVG polyline's. Each chart keeps its own height, and its own
 * way across: through a day, a run's days or a grid run.
 */

/** Every chart's width, in its `viewBox`'s units. */
export const CHART_WIDTH = 240;
/** The decimals a point is written to. */
export const POINT_DECIMALS = 1;

/** The lowest and highest values a chart spans, foot to head. */
export interface ChartRange {
  min: number;
  max: number;
}

/** How far down a chart `height` tall a value lies: the range's least at
 * its foot, its most at its head, and every value in the middle when the
 * range is one value. */
export function chartY(value: number, { min, max }: ChartRange, height: number): number {
  return min === max ? height / 2 : height - ((value - min) / (max - min)) * height;
}

/** An SVG polyline's points, each at its `xs` across and its value up the
 * range: a value missing reads as the range's least. */
export function polylinePoints(
  xs: readonly number[],
  values: readonly number[],
  range: ChartRange,
  height: number,
): string {
  return xs
    .map((x, index) => {
      const y = chartY(values[index] ?? range.min, range, height);
      return `${x.toFixed(POINT_DECIMALS)},${y.toFixed(POINT_DECIMALS)}`;
    })
    .join(" ");
}
