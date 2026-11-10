import { ColourBy } from "./ColourBy";
import type { OverlayToggles, SceneOverlay } from "./debug/overlays";
import { Fold } from "./design/Fold";
import type { FieldView } from "./fields/display";
import { useFolds } from "./folds";
import { PanelCard } from "./PanelCard";

// What each overlay over the scene is called beside its switch; the air
// field is called by how it is drawn.
const SCENE_OVERLAY_LABELS: Record<Exclude<SceneOverlay, "airField">, string> = {
  openingFlows: "Flows through openings",
  wind: "Wind",
  sun: "Sun and its path",
  cameraViews: "Camera views",
  probes: "Probes",
};

// What the switches change, apart from the equipment's, which change the run.
// It is the group's tooltip, not a line of its own: the info panel shows all
// of itself at the usual window size beside the tallest legend.
const VIEW_ONLY = "Hiding one changes only the view, never the run or its equipment.";

function overlayLabel(overlay: SceneOverlay, fieldView: FieldView): string {
  return overlay === "airField" ? `Air field ${fieldView}` : SCENE_OVERLAY_LABELS[overlay];
}

/** How the scene is drawn, in a line, as its section folded says it (#273): its
 * colouring, and whether by category and with its dimensions. */
export function describeColours(
  colourBy: string | null,
  switches: { showDimensions: boolean; byCategory: boolean },
): string {
  return [
    `Colours: ${colourBy === null ? "their own" : `by ${colourBy}`}`,
    ...(switches.byCategory ? ["by category"] : []),
    ...(switches.showDimensions ? ["dimensions shown"] : []),
  ].join(", ");
}

/** Which of the overlays over the scene are shown, in a line, as their section
 * folded says it: those hidden, every one being shown at first. */
export function describeOverlays(hidden: readonly string[]): string {
  const hiding = hidden.map((label) => label.charAt(0).toLowerCase() + label.slice(1));
  return hiding.length === 0 ? "Overlays: all shown" : `Overlays: hiding ${hiding.join(", ")}`;
}

/** The *Display* card (P22.8): how the scene is shown, in its sections, each
 * folded to the line that says how it stands, as the house's are: its colours,
 * by a property or by category, and its dimensions; which overlays are drawn
 * over it; and whether the viewer is in QA mode (P09.6), which shows what the
 * simulator knows and a policy never sees. */
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
  const fold = useFolds<"display" | "overlays">();
  return (
    <PanelCard title="Display">
      <Fold
        className="display-fold"
        {...fold("display")}
        summary={
          <span data-testid="display-summary">
            {describeColours(colourBy, { showDimensions, byCategory })}
          </span>
        }
      >
        {colourProperties.length > 0 && (
          <ColourBy properties={colourProperties} value={colourBy} onChange={onColourBy} />
        )}
        <p>
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
              checked={showDimensions}
              onChange={(event) => onShowDimensions(event.target.checked)}
            />{" "}
            Dimensions and axis labels
          </label>
        </p>
      </Fold>
      {drawn.length > 0 && (
        <Fold
          className="display-overlays"
          {...fold("overlays")}
          summary={
            <span data-testid="overlays-summary">
              {describeOverlays(
                drawn
                  .filter((overlay) => !overlays[overlay])
                  .map((overlay) => overlayLabel(overlay, fieldView)),
              )}
            </span>
          }
        >
          <fieldset className="shown-overlays" title={VIEW_ONLY}>
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
          </fieldset>
        </Fold>
      )}
      <p className="display-qa">
        <label>
          <input
            type="checkbox"
            checked={qaMode}
            onChange={(event) => onQaMode(event.target.checked)}
          />{" "}
          QA mode
        </label>
      </p>
    </PanelCard>
  );
}
