// @vitest-environment jsdom
import { act } from "react";
import { MOUSE, PerspectiveCamera, TOUCH } from "three";
import { afterEach, describe, expect, it } from "vitest";

import { CONTROLS, ControlsHelp } from "./ControlsHelp";
import { orbitControls } from "./orbit";
import { button, click, type Rendered, render } from "./testing/render";

function press(key: string, target: EventTarget = window): void {
  act(() => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  });
}

function said(within: ParentNode, device: string): string[] {
  return [...within.querySelectorAll(`[data-testid="controls-${device}"] dt`)].map(
    (term) => `${term.textContent}: ${term.nextElementSibling?.textContent}`,
  );
}

describe("the view's controls, listed", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  it("opens from its button, closes with ×, and opens again", () => {
    shown = render(<ControlsHelp />);
    const { container } = shown;

    click(button(container, "Controls ?"));
    expect(container.querySelector("h2")?.textContent).toBe("Moving around the view");
    expect(said(container, "mouse")).toContain("Drag: orbit around the point in view");
    expect(said(container, "mouse")).toContain("Shift-, Ctrl- or ⌘-drag, or right-drag: pan");

    click(button(container, "Close the controls"));
    expect(container.querySelector(".controls-help")).toBeNull();
    click(button(container, "Controls ?"));
    expect(container.querySelector(".controls-help")).not.toBeNull();
  });

  it("opens with ?, closes with Escape, its focus going there and back", () => {
    shown = render(<ControlsHelp />);
    const { container } = shown;

    press("?");
    const close = button(container, "Close the controls");
    expect(document.activeElement).toBe(close);
    press("Escape");
    expect(container.querySelector(".controls-help")).toBeNull();
    expect(document.activeElement).toBe(button(container, "Controls ?"));
    // ? again opens it, and ? once more closes it.
    press("?");
    press("?");
    expect(container.querySelector(".controls-help")).toBeNull();
  });

  it("takes no ? typed into a field", () => {
    shown = render(
      <>
        <input aria-label="probe height" />
        <ControlsHelp />
      </>,
    );
    const field = shown.container.querySelector("input");
    if (field === null) {
      throw new Error("no field");
    }

    press("?", field);

    expect(shown.container.querySelector(".controls-help")).toBeNull();
  });

  it("lists what the view's controls do, and nothing they do not", () => {
    const element = document.createElement("div");
    document.body.append(element);
    const camera = new PerspectiveCamera();
    camera.position.set(5, -5, 5);
    const { orbit, dispose } = orbitControls(camera, element);
    try {
      // three's own bindings, which the list describes: a drag orbits, a
      // right-drag pans (as a modified drag does), the middle button zooms;
      // one finger orbits, two zoom and pan.
      expect(orbit.mouseButtons).toEqual({
        LEFT: MOUSE.ROTATE,
        MIDDLE: MOUSE.DOLLY,
        RIGHT: MOUSE.PAN,
      });
      expect(orbit.touches).toEqual({ ONE: TOUCH.ROTATE, TWO: TOUCH.DOLLY_PAN });
      expect(orbit.enablePan && orbit.enableRotate && orbit.enableZoom).toBe(true);
      // No keys move the view: the list offers none.
      const before = camera.position.clone();
      for (const key of ["ArrowLeft", "ArrowUp", "ArrowRight", "ArrowDown"]) {
        for (const target of [element, window]) {
          target.dispatchEvent(new KeyboardEvent("keydown", { key, code: key, bubbles: true }));
        }
      }
      orbit.update();
      expect(camera.position.toArray()).toEqual(before.toArray());
    } finally {
      dispose();
      element.remove();
    }
    const keys = CONTROLS.find(({ device }) => device === "Keyboard")?.controls ?? [];
    expect(keys.map(({ input }) => input)).toEqual(["?", "Tab, then Enter or Space"]);
  });
});
