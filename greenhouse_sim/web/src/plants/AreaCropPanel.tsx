import { CHART_WIDTH, type ChartRange, polylinePoints } from "../charts/chart";
import { dayCount } from "../clock";
import { Fold } from "../design/Fold";
import { Notice } from "../design/Notice";
import type { Fold as FoldState } from "../folds";
import { runApartFromItsMoment, type ScenarioRun } from "../scene/run";
import { drawn, useLoadProgress } from "../useLoad";
import {
  type AreaCropCourse,
  type AreaCropState,
  type AreaQuantityCourse,
  areaCropUrl,
  loadAreaCrop,
} from "./areaCrop";
import type { AreaBasis } from "./generated/areaCropTypes";

// Each quantity's chart, in its own units.
const HEIGHT = 28;
// A value is written to three significant digits, and in whole units from
// a hundred up, never in powers of ten: 0.0787, 2.80, 16.9, 44641.
const SIGNIFICANT_DIGITS = 3;
const WHOLE_FROM = 100;
// What the folded line says of the crop, if the model charts it: the leaf
// area index, which both models grown by area give; or else its first
// quantity.
const SUMMARISED = "lai";
// The area its quantities are per m² of, in words.
const BASES: Readonly<Record<AreaBasis, string>> = {
  floor: "floor",
  cultivated: "cultivated ground",
};

/** A value in the model's unit, to three significant digits. */
export function written(value: number): string {
  return Math.abs(value) >= WHOLE_FROM ? value.toFixed(0) : value.toPrecision(SIGNIFICANT_DIGITS);
}

/** A quantity at the moment shown, in words: the house's, and its rows'
 * least and most, "Leaf area index 1.19 m² m⁻², rows 1.13 to 1.24", or
 * "rows alike" where they agree. */
export function describeQuantity(quantity: AreaQuantityCourse): string {
  const house = written(quantity.house.at(-1) ?? 0);
  const least = written(quantity.least.at(-1) ?? 0);
  const most = written(quantity.most.at(-1) ?? 0);
  const rows = least === most ? "rows alike" : `rows ${least} to ${most}`;
  return `${quantity.name} ${house} ${quantity.unit}, ${rows}`;
}

/** The crop grown by area in a line, as its section folded says how it
 * stands: after how many days, and its leaf area index then. */
export function describeAreaCrop(state: AreaCropState): string {
  switch (state.status) {
    case "none":
      return "Crop by area";
    case "loading":
      return "Crop by area: growing…";
    case "unavailable":
      return "Crop by area: cannot be read";
    case "loaded": {
      const { course } = state;
      const shown = course.quantities.find(({ key }) => key === SUMMARISED) ?? course.quantities[0];
      const lived = `Crop by area after ${dayCount(course.days.at(-1) ?? 0)}`;
      if (shown === undefined) {
        return lived;
      }
      const value = written(shown.house.at(-1) ?? 0);
      return `${lived}: ${shown.name.toLowerCase()} ${value} ${shown.unit}`;
    }
  }
}

/** What a course's values are, as decision 0062 asks them labelled: its
 * model's predictions, per m² of its basis, of the house and of its rows. */
export function predictionsLabel(course: AreaCropCourse): string {
  const last = course.days.at(-1) ?? 0;
  const lived = last === 0 ? "As planted, no day lived yet" : `After ${dayCount(last)}`;
  return (
    `${lived}: the ${course.model} model's predictions, per m² of ${BASES[course.basis]} ` +
    `unless a unit says otherwise. Each line is the house's, its ${course.rows} rows weighted ` +
    "by their areas; behind it, the rows' least to most."
  );
}

/** A chart's points across its days, from the first to the last. */
function across(days: readonly number[]): number[] {
  const last = Math.max(1, days.at(-1) ?? 1);
  return days.map((day) => (day / last) * CHART_WIDTH);
}

/** The rows' least to most as an SVG polygon's points: along the least,
 * then back along the most. */
function band(xs: readonly number[], quantity: AreaQuantityCourse, range: ChartRange): string {
  return [
    polylinePoints(xs, quantity.least, range, HEIGHT),
    polylinePoints([...xs].reverse(), [...quantity.most].reverse(), range, HEIGHT),
  ].join(" ");
}

function Charts({ course }: { course: AreaCropCourse }) {
  const xs = across(course.days);
  // A chart needs two days to draw a line: the first day's values are the
  // crop as its model plants it.
  const charted = course.days.length > 1;
  return (
    <figure className="crop-area" data-testid="area-crop" aria-label="Crop by area">
      <figcaption className="crop-area-note">{predictionsLabel(course)}</figcaption>
      {course.quantities.map((quantity) => {
        const range = { min: Math.min(...quantity.least), max: Math.max(...quantity.most) };
        const name = quantity.name.toLowerCase();
        return (
          <div className="house-air-row" key={quantity.key}>
            <span data-testid={`area-crop-${quantity.key}`}>{describeQuantity(quantity)}</span>
            {charted && (
              <svg
                className="house-air-chart"
                viewBox={`0 0 ${CHART_WIDTH} ${HEIGHT}`}
                preserveAspectRatio="none"
                role="img"
                aria-label={`The house's ${name} after each day, in ${quantity.unit}, its rows' least to most behind it`}
              >
                <polygon className="crop-area-band" points={band(xs, quantity, range)} />
                <polyline
                  className="crop-area-house"
                  points={polylinePoints(xs, quantity.house, range, HEIGHT)}
                />
              </svg>
            )}
          </div>
        );
      })}
    </figure>
  );
}

/**
 * A crop grown by area through the run's days up to the moment drawn
 * (decision 0083), which the scene does not draw: for each quantity its
 * model charts, the house's value at each day's start, its rows' least to
 * most behind it, and its value then, labelled as the model's predictions.
 */
export function AreaCrop({ state }: { state: AreaCropState }) {
  switch (state.status) {
    case "none":
      return null;
    case "loading":
      return (
        <p className="crop-area" data-testid="area-crop">
          Growing the crop's days…
        </p>
      );
    case "unavailable":
      return (
        <Notice kind="problem" className="crop-area" data-testid="area-crop">
          The crop's days cannot be read: {state.reason}.
        </Notice>
      );
    case "loaded":
      return <Charts course={state.course} />;
  }
}

/**
 * The scenario's crop grown by area as a section folded to its line, asked
 * for once it is opened and nothing while it is folded; the last course
 * shown stays on show while the next day's is on its way, within one run.
 */
export function AreaCropPanel({ run, fold }: { run: ScenarioRun; fold: FoldState }) {
  const progress = useLoadProgress(fold.open ? areaCropUrl(run) : null, loadAreaCrop, {
    group: runApartFromItsMoment(run),
  });
  const state = drawn(progress);
  return (
    <Fold
      className="crop-area-fold"
      {...fold}
      summary={<span data-testid="area-crop-summary">{describeAreaCrop(state)}</span>}
    >
      <AreaCrop state={state} />
    </Fold>
  );
}
