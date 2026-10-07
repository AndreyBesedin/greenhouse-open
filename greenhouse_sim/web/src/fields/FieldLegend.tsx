import { SCALAR_STOPS, type ScalarRange } from "../debug/scalar";
import { formatValue } from "../readouts";

/** What a field's colours mean: the quantity, its unit, and the range the
 * colours run over, which the viewer may narrow or widen; reset returns it to
 * the field's own. */
export function FieldLegend({
  title,
  unit,
  range,
  own,
  onRange,
}: {
  title: string;
  unit: string;
  range: ScalarRange;
  /** The field's own range for the quantity. */
  own: ScalarRange;
  onRange: (range: ScalarRange | null) => void;
}) {
  const gradient = `linear-gradient(to right, ${SCALAR_STOPS.join(", ")})`;
  const changed = range.min !== own.min || range.max !== own.max;
  const set = (end: "min" | "max", text: string) => {
    const value = Number(text);
    if (text !== "" && Number.isFinite(value)) {
      onRange({ ...range, [end]: value });
    }
  };
  return (
    <figure className="scalar-legend field-legend" aria-label="Field legend">
      <figcaption data-testid="field-legend-quantity">
        {title} ({unit})
      </figcaption>
      <div className="scalar-bar" style={{ background: gradient }} />
      <div className="scalar-ticks">
        <input
          aria-label="Lowest colour"
          type="number"
          step="any"
          value={formatValue(range.min)}
          onChange={(event) => set("min", event.target.value)}
        />
        <input
          aria-label="Highest colour"
          type="number"
          step="any"
          value={formatValue(range.max)}
          onChange={(event) => set("max", event.target.value)}
        />
      </div>
      {changed && (
        <button type="button" onClick={() => onRange(null)}>
          The field's own range
        </button>
      )}
    </figure>
  );
}
