import { ColourBy } from "./ColourBy";

/** How the scene is shown: shaded by a property, and measured. */
export function DisplayOptions({
  colourProperties,
  colourBy,
  onColourBy,
  showDimensions,
  onShowDimensions,
  byCategory,
  onByCategory,
}: {
  colourProperties: readonly string[];
  colourBy: string | null;
  onColourBy: (property: string | null) => void;
  showDimensions: boolean;
  onShowDimensions: (show: boolean) => void;
  byCategory: boolean;
  onByCategory: (show: boolean) => void;
}) {
  return (
    <>
      {colourProperties.length > 0 && (
        <ColourBy properties={colourProperties} value={colourBy} onChange={onColourBy} />
      )}
      <p>
        <label>
          <input
            type="checkbox"
            checked={showDimensions}
            onChange={(event) => onShowDimensions(event.target.checked)}
          />{" "}
          Dimensions and axis labels
        </label>{" "}
        <label>
          <input
            type="checkbox"
            checked={byCategory}
            onChange={(event) => onByCategory(event.target.checked)}
          />{" "}
          Categories
        </label>
      </p>
    </>
  );
}
