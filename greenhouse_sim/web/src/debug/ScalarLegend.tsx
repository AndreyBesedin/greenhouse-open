import { formatValue } from "../readouts";
import { type Colouring, SCALAR_STOPS } from "./scalar";

/** What the colours mean while entities are shaded by a property. */
export function ScalarLegend({ colouring }: { colouring: Colouring }) {
  const gradient = `linear-gradient(to right, ${SCALAR_STOPS.join(", ")})`;
  return (
    <figure className="scalar-legend" aria-label="Legend">
      <figcaption data-testid="legend-property">{colouring.property}</figcaption>
      <div className="scalar-bar" style={{ background: gradient }} />
      <div className="scalar-ticks">
        <span data-testid="legend-min">{formatValue(colouring.range.min)}</span>
        <span data-testid="legend-max">{formatValue(colouring.range.max)}</span>
      </div>
    </figure>
  );
}
