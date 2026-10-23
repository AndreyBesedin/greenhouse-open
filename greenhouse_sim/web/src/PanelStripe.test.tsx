// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { PanelStripe } from "./PanelStripe";
import { type PanelSide, storedFolds, usePanelFolds } from "./panelFolds";
import { button, type Rendered, render } from "./testing/render";

/** Both sides' stripes, as the viewer lays them out, folding what they say. */
function Sides() {
  const [folded, toggle] = usePanelFolds();
  return (
    <>
      {(["info", "view"] as PanelSide[]).map((side) => (
        <div key={side} data-folded={folded.has(side)}>
          <PanelStripe side={side} folded={folded.has(side)} onToggle={() => toggle(side)} />
        </div>
      ))}
    </>
  );
}

describe("the panels' stripes (#304)", () => {
  let shown: Rendered | undefined;
  afterEach(() => {
    shown?.unmount();
    localStorage.clear();
  });

  it("fold each side's panels towards the screen's edge, and open them again", () => {
    shown = render(<Sides />);
    const info = button(shown.container, "Fold the info panel");
    const view = button(shown.container, "Fold the View panel");
    // Open, each arrow points to its side's edge.
    expect([info.textContent, view.textContent]).toEqual(["◀", "▶"]);
    expect(info.getAttribute("aria-expanded")).toBe("true");

    act(() => info.click());

    const opener = button(shown.container, "Open the info panel");
    expect(opener.textContent).toBe("▶");
    expect(opener.getAttribute("aria-expanded")).toBe("false");
    expect(storedFolds()).toEqual(new Set(["info"]));
    // The other side stays as it was.
    expect(button(shown.container, "Fold the View panel").textContent).toBe("▶");

    act(() => opener.click());
    expect(button(shown.container, "Fold the info panel").textContent).toBe("◀");
    expect(storedFolds()).toEqual(new Set());
  });

  it("keep the sides folded for the next visit, and nothing else", () => {
    localStorage.setItem("greenhouse-sim.folded", "view,elsewhere");
    expect(storedFolds()).toEqual(new Set(["view"]));

    shown = render(<Sides />);

    expect(button(shown.container, "Open the View panel").textContent).toBe("◀");
    expect(button(shown.container, "Fold the info panel").textContent).toBe("◀");
  });
});
