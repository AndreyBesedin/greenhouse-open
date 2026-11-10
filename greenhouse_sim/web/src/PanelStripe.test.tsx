// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { PanelStripe } from "./PanelStripe";
import { type PanelSide, storedFolds, usePanelFolds, useTransportFold } from "./panelFolds";
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

/** A replay's stripe under the view, folding its controls (P22.9). */
function Transport() {
  const [folded, toggle] = useTransportFold();
  return <PanelStripe side="transport" folded={folded} onToggle={toggle} />;
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

  it("keep a replay's controls folded beside the viewer's sides, neither losing the other's", () => {
    shown = render(
      <>
        <Sides />
        <Transport />
      </>,
    );
    act(() => button(shown?.container as HTMLElement, "Fold the info panel").click());
    act(() => button(shown?.container as HTMLElement, "Fold the controls under the view").click());
    expect(storedFolds()).toEqual(new Set(["info", "transport"]));

    // The viewer's side opened again leaves the replay's controls folded.
    act(() => button(shown?.container as HTMLElement, "Open the info panel").click());
    expect(storedFolds()).toEqual(new Set(["transport"]));
    shown.unmount();

    shown = render(<Transport />);
    const open = button(shown.container, "Open the controls under the view");
    // Folded, its arrow points up, the way it opens; open, down, the way it folds.
    expect(open.textContent).toBe("▲");
    expect(open.title).toBe("Open the controls under the view");
    act(() => open.click());
    expect(button(shown.container, "Fold the controls under the view").textContent).toBe("▼");
    expect(storedFolds()).toEqual(new Set());
  });

  it("stand as tall as the panel beside them, never shorter than their tab", () => {
    const toggle = () => undefined;
    const height = (heightPx: number | null) => {
      shown?.unmount();
      shown = render(
        <PanelStripe side="info" folded={false} onToggle={toggle} heightPx={heightPx} />,
      );
      return button(shown.container, "Fold the info panel").style.height;
    };
    expect(height(312.5)).toBe("312.5px");
    expect(height(40)).toBe("96px");
    // Until the panel is measured, the stylesheet's tab.
    expect(height(null)).toBe("");
  });

  it("keep the sides folded for the next visit, and nothing else", () => {
    localStorage.setItem("greenhouse-sim.folded", "view,elsewhere");
    expect(storedFolds()).toEqual(new Set(["view"]));

    shown = render(<Sides />);

    expect(button(shown.container, "Open the View panel").textContent).toBe("◀");
    expect(button(shown.container, "Fold the info panel").textContent).toBe("◀");
  });
});
