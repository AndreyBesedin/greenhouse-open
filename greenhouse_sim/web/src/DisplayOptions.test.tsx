// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { DisplayOptions, describeColours, describeOverlays } from "./DisplayOptions";
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
    expect(shown.querySelector("fieldset")?.title).toBe(
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

  it("say on the section's line which of them are hidden (#273)", () => {
    const shown = options({ ...ALL_OVERLAYS, wind: false, probes: false }, [
      "airField",
      "wind",
      "probes",
    ]);
    expect(shown.querySelector(".display-overlays > summary")?.textContent).toBe(
      "Overlays: hiding wind, probes",
    );
  });

  it("offer no switches while nothing is drawn over the scene", () => {
    expect(options(ALL_OVERLAYS, []).querySelector("fieldset")).toBeNull();
  });
});

describe("the Display card's sections, folded (P22.8)", () => {
  it("say how the scene is coloured, and the switches on (#273)", () => {
    const off = { showDimensions: false, byCategory: false };
    expect(describeColours(null, off)).toBe("Colours: their own");
    expect(describeColours("level", { showDimensions: true, byCategory: true })).toBe(
      "Colours: by level, by category, dimensions shown",
    );
  });

  it("name the overlays hidden, every one being shown at first", () => {
    expect(describeOverlays([])).toBe("Overlays: all shown");
    expect(describeOverlays(["Wind", "Air field arrows"])).toBe(
      "Overlays: hiding wind, air field arrows",
    );
  });

  it("stand in a card of their own, folded to their lines at first, QA mode beside them", () => {
    const shown = render(
      <DisplayOptions
        colourProperties={[]}
        colourBy={null}
        onColourBy={ignore}
        showDimensions={false}
        onShowDimensions={ignore}
        byCategory={false}
        onByCategory={ignore}
        drawn={["wind"]}
        fieldView="arrows"
        overlays={ALL_OVERLAYS}
        onOverlays={ignore}
        qaMode={false}
        onQaMode={ignore}
      />,
    );
    try {
      const card = shown.container.querySelector("section.panel-card");
      expect(card?.querySelector("h2")?.textContent).toBe("Display");
      const folds = [...(card?.querySelectorAll(":scope > details") ?? [])];
      expect(folds.map((fold) => fold.className)).toEqual([
        "ds-fold display-fold",
        "ds-fold display-overlays",
      ]);
      expect(folds.every((fold) => !fold.hasAttribute("open"))).toBe(true);
      expect(folds.map((fold) => fold.querySelector("summary")?.textContent)).toEqual([
        "Colours: their own",
        "Overlays: all shown",
      ]);
      expect(checkbox(card as HTMLElement, "QA mode").closest("details")).toBeNull();
    } finally {
      shown.unmount();
    }
  });
});
