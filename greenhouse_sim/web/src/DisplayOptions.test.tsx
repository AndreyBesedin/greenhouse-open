// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { DisplayOptions } from "./DisplayOptions";
import { ALL_OVERLAYS, type OverlayToggles, type SceneOverlay } from "./debug/overlays";
import type { FieldView } from "./fields/display";
import { checkbox, click, type Rendered, render } from "./testing/render";

const ignore = () => undefined;

describe("the display options", () => {
  let drawn: Rendered | undefined;
  afterEach(() => {
    drawn?.unmount();
    drawn = undefined;
  });

  // Draws the options afresh, in place of any drawn before.
  function options(
    overlays: OverlayToggles,
    over: readonly SceneOverlay[],
    fieldView: FieldView = "arrows",
    onOverlays: (overlays: OverlayToggles) => void = ignore,
  ): HTMLElement {
    drawn?.unmount();
    drawn = render(
      <DisplayOptions
        colourProperties={[]}
        colourBy={null}
        onColourBy={ignore}
        showDimensions={false}
        onShowDimensions={ignore}
        byCategory={false}
        onByCategory={ignore}
        drawn={over}
        fieldView={fieldView}
        overlays={overlays}
        onOverlays={onOverlays}
        qaMode={false}
        onQaMode={ignore}
      />,
    );
    return drawn.container;
  }

  it("give each overlay drawn over the scene a switch, named for what it shows", () => {
    const over: SceneOverlay[] = ["airField", "wind", "probes"];
    const shown = options({ ...ALL_OVERLAYS, wind: false }, over, "streamlines");
    const labels = [...shown.querySelectorAll("fieldset label")].map((l) => l.textContent?.trim());

    expect(shown.querySelector("fieldset legend")?.textContent).toBe("Shown in the view");
    expect(labels).toEqual(["Air field streamlines", "Wind", "Probes"]);
    expect(checkbox(shown, "Wind").checked).toBe(false);
    expect(checkbox(shown, "Probes").checked).toBe(true);
    // Unlike the equipment's switches, which change the run.
    expect(shown.querySelector("fieldset p")?.textContent).toBe(
      "Hiding one changes only the view, never the run or its equipment.",
    );
  });

  it("hide an overlay, or show it again, and change no other switch", () => {
    const onOverlays = vi.fn();
    const over: SceneOverlay[] = ["sun", "cameraViews", "probes"];
    const shown = options({ ...ALL_OVERLAYS, probes: false }, over, "arrows", onOverlays);

    click(checkbox(shown, "Sun and its path"));
    click(checkbox(shown, "Probes"));

    expect(onOverlays.mock.calls).toEqual([
      [{ ...ALL_OVERLAYS, probes: false, sun: false }],
      [ALL_OVERLAYS],
    ]);
  });

  it("name the air field's switch by how it is drawn", () => {
    for (const fieldView of ["arrows", "slice"] as const) {
      const shown = options(ALL_OVERLAYS, ["airField"], fieldView);

      expect(checkbox(shown, `Air field ${fieldView}`).checked).toBe(true);
    }
  });

  it("offer no switches while nothing is drawn over the scene", () => {
    expect(options(ALL_OVERLAYS, []).querySelector("fieldset")).toBeNull();
  });
});
