import { CHART_WIDTH, polylinePoints } from "../charts/chart";
import type { CropPlant, CropPlantState, PlantDay } from "./crop";
import { PlantHistory, PlantTree } from "./PlantStructure";

// Each quantity's chart across the days lived, in its own units.
const HEIGHT = 28;
const CHARTED: readonly {
  key: string;
  name: string;
  unit: string;
  decimals: number;
  of: (day: PlantDay) => number;
}[] = [
  { key: "air", name: "Air", unit: "°C", decimals: 1, of: (day) => day.temperature },
  { key: "light", name: "Light", unit: "mol/m²/d", decimals: 1, of: (day) => day.light },
  { key: "co2", name: "CO₂", unit: "ppm", decimals: 0, of: (day) => day.co2 },
];

function polyline(values: number[], low: number, high: number): string {
  // A day's value across its share of the days, so a single day is a line.
  const x = (index: number) => (index / values.length) * CHART_WIDTH;
  return polylinePoints(
    values.flatMap((_, index) => [x(index), x(index + 1)]),
    values.flatMap((value) => [value, value]),
    { min: low, max: high },
    HEIGHT,
  );
}

/** A quantity of a plant's days in words: its last day's, and its range
 * over the days lived, "Light 22.9 mol/m²/d on day 4, 19.8 to 23.1". */
export function describeDays(
  values: number[],
  name: string,
  unit: string,
  decimals: number,
): string {
  const last = values.at(-1) ?? 0;
  const low = Math.min(...values).toFixed(decimals);
  const high = Math.max(...values).toFixed(decimals);
  return `${name} ${last.toFixed(decimals)} ${unit} on day ${values.length - 1}, ${low} to ${high}`;
}

function Days({ plant }: { plant: CropPlant }) {
  if (plant.days === 0) {
    return (
      <p className="plant-days" data-testid="plant-days">
        No day lived yet: the plant lives each day at the midnight that ends it.
      </p>
    );
  }
  return (
    <figure className="plant-days" data-testid="plant-days" aria-label="Plant days">
      <figcaption>Days lived: {plant.days}, each in the house's air and its own light</figcaption>
      {CHARTED.map(({ key, name, unit, decimals, of }) => {
        const values = plant.environments.map(of);
        const low = Math.min(...values);
        const high = Math.max(...values);
        return (
          <div className="house-air-row" key={key}>
            <span data-testid={`plant-days-${key}`}>
              {describeDays(values, name, unit, decimals)}
            </span>
            <svg
              className="house-air-chart"
              viewBox={`0 0 ${CHART_WIDTH} ${HEIGHT}`}
              preserveAspectRatio="none"
              role="img"
              aria-label={`The plant's ${name.toLowerCase()} day by day`}
            >
              <polyline className="house-air-run" points={polyline(values, low, high)} />
            </svg>
          </div>
        );
      })}
    </figure>
  );
}

/**
 * A plant of a run's crop as it stands at the moment drawn: what it
 * experienced each day it lived, charted day by day, what was done to it,
 * and its structure, organ by organ.
 */
export function PlantDays({
  state,
  selectedOrgan,
  onSelect,
}: {
  state: CropPlantState;
  /** The organ the selected entity draws part of. */
  selectedOrgan: string | null;
  onSelect: (organId: string) => void;
}) {
  switch (state.status) {
    case "none":
      return null;
    case "loading":
      return (
        <p className="plant-days" data-testid="plant-days">
          Growing the plant's days…
        </p>
      );
    case "unavailable":
      return (
        <p className="plant-days" data-testid="plant-days" role="alert">
          The plant's days are not available: {state.reason}.
        </p>
      );
    case "loaded": {
      const { plant } = state;
      return (
        <>
          <Days plant={plant} />
          <PlantHistory plantId={plant.plantId} history={plant.history} />
          <PlantTree
            plantId={plant.plantId}
            tree={plant.tree}
            selectedOrgan={selectedOrgan}
            onSelect={onSelect}
          />
        </>
      );
    }
  }
}
