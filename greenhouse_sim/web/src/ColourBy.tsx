// The choice that keeps every entity in the colour the simulator gave it.
const OWN_COLOURS = "";

/** Chooses a numeric property to shade the scene's entities by. */
export function ColourBy({
  properties,
  value,
  onChange,
}: {
  properties: readonly string[];
  value: string | null;
  onChange: (property: string | null) => void;
}) {
  return (
    <p>
      <label>
        Colour by{" "}
        <select
          value={value ?? OWN_COLOURS}
          onChange={(event) =>
            onChange(event.target.value === OWN_COLOURS ? null : event.target.value)
          }
        >
          <option value={OWN_COLOURS}>own colours</option>
          {properties.map((property) => (
            <option key={property} value={property}>
              {property}
            </option>
          ))}
        </select>
      </label>
    </p>
  );
}
