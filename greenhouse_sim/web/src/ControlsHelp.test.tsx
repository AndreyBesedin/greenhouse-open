// @vitest-environment jsdom
import { act } from "react";
import { MOUSE, PerspectiveCamera, TOUCH } from "three";
import { afterEach, describe, expect, it } from "vitest";

import { CONTROLS, ControlsHelp } from "./ControlsHelp";
import { PLACE_BY_CLICKING } from "./fields/FieldProbes";
import { MovePanel } from "./MovePanel";
import { orbitControls } from "./orbit";
import { button, click, type Rendered, render } from "./testing/render";

function press(key: string, target: EventTarget = window): void {
  act(() => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  });
}

function said(within: ParentNode, section: string): string[] {
  return [...within.querySelectorAll(`[data-testid="controls-${section}"] dt`)].map(
    (term) => `${term.textContent}: ${term.nextElementSibling?.textContent}`,
  );
}

/** An action's inputs as the card lists them, by device. */
function inputsOf(within: ParentNode, action: string): Record<string, string> {
  const term = [...within.querySelectorAll("dt")].find((each) => each.textContent === action);
  const items = term?.parentElement?.querySelectorAll(".controls-inputs li") ?? [];
  return Object.fromEntries(
    [...items].map((item) => {
      const device = item.querySelector(".controls-device")?.textContent ?? "";
      return [device, (item.textContent ?? "").slice(device.length).trim()];
    }),
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
    expect(said(container, "camera")).toContain("Orbit: around the point in view");
    expect(inputsOf(container, "Pan").Mouse).toBe("Shift-, Ctrl- or ⌘-drag, or right-drag");

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

  it("lists each action once, orbit, pan and zoom with each device's inputs (#272)", () => {
    shown = render(<ControlsHelp />);
    const { container } = shown;
    click(button(container, "Controls ?"));

    const actions = [...container.querySelectorAll("dt")].map((term) => term.textContent);
    expect(new Set(actions).size).toBe(actions.length);
    for (const action of ["Orbit", "Pan", "Zoom"]) {
      expect(Object.keys(inputsOf(container, action))).toEqual(["Mouse", "Trackpad", "Touch"]);
    }
    // A mouse's middle button zooms; a trackpad has none, and lists none.
    expect(inputsOf(container, "Zoom").Mouse).toContain("middle-drag");
    expect(JSON.stringify(inputsOf(container, "Zoom").Trackpad)).not.toContain("middle");
  });

  it("says how to start each mode it lists, by the controls that do", () => {
    shown = render(<ControlsHelp />);
    const { container } = shown;
    click(button(container, "Controls ?"));
    const inView = said(container, "in-the-view");

    expect(inView).toContain(
      `Place a probe: with an air field shown, tick “${PLACE_BY_CLICKING}” in the Probes section, then click the floor`,
    );
    const moving = inView.find((line) => line.startsWith("Move equipment or a sensor"));
    expect(moving).toContain("select it, press Move in the inspector, then drag");
    // The inspector's button is called so.
    const inspector = render(
      <MovePanel
        label="heater"
        moving={false}
        movedBy={null}
        canUndo={false}
        onMoving={() => undefined}
        onUndo={() => undefined}
        onPutBack={() => undefined}
      />,
    );
    try {
      expect(button(inspector.container, "Move")).toBeTruthy();
    } finally {
      inspector.unmount();
    }
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
    const keys = CONTROLS.find(({ section }) => section === "Keyboard")?.actions ?? [];
    expect(keys.map(({ action }) => action)).toEqual(["?", "Escape", "Tab, then Enter or Space"]);
  });
});
