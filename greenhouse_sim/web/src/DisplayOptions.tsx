import { ColourBy } from "./ColourBy";
import type { OverlayToggles, SceneOverlay } from "./debug/overlays";
import type { FieldView } from "./fields/display";

// What each overlay over the scene is called beside its switch; the air
// field is called by how it is drawn.
const SCENE_OVERLAY_LABELS: Record<Exclude<SceneOverlay, "airField">, string> = {
  openingFlows: "Flows through openings",
  wind: "Wind",
  sun: "Sun and its path",
  cameraViews: "Camera views",
  probes: "Probes",
};

function overlayLabel(overlay: SceneOverlay, fieldView: FieldView): string {
  return overlay === "airField" ? `Air field ${fieldView}` : SCENE_OVERLAY_LABELS[overlay];
}

/** How the scene is shown: shaded by a property, and measured; which of the
 * overlays over it are drawn; and whether the viewer is in QA mode (P09.6),
 * which shows what the simulator knows and a policy never sees. */
export function DisplayOptions({
  colourProperties,
  colourBy,
  onColourBy,
  showDimensions,
  onShowDimensions,
  byCategory,
  onByCategory,
  drawn,
  fieldView,
  overlays,
  onOverlays,
  qaMode,
  onQaMode,
}: {
  colourProperties: readonly string[];
  colourBy: string | null;
  onColourBy: (property: string | null) => void;
  showDimensions: boolean;
  onShowDimensions: (show: boolean) => void;
  byCategory: boolean;
  onByCategory: (show: boolean) => void;
  /** The overlays over the scene that have something to draw, shown or not. */
  drawn: readonly SceneOverlay[];
  /** How the air field is drawn, which names its switch. */
  fieldView: FieldView;
  overlays: OverlayToggles;
  onOverlays: (overlays: OverlayToggles) => void;
  qaMode: boolean;
  onQaMode: (on: boolean) => void;
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
        </label>{" "}
        <label>
          <input
            type="checkbox"
            checked={qaMode}
            onChange={(event) => onQaMode(event.target.checked)}
          />{" "}
          QA mode
        </label>
      </p>
      {drawn.length > 0 && (
        // Named for what is seen, apart from the equipment's switches, which
        // change the run: these change only the view.
        <fieldset className="shown-overlays">
          <legend>Shown in the view</legend>
          {drawn.map((overlay) => (
            <label key={overlay}>
              <input
                type="checkbox"
                checked={overlays[overlay]}
                onChange={(event) => onOverlays({ ...overlays, [overlay]: event.target.checked })}
              />{" "}
              {overlayLabel(overlay, fieldView)}
            </label>
          ))}
          <p>Hiding one changes only the view, never the run or its equipment.</p>
        </fieldset>
      )}
    </>
  );
}
