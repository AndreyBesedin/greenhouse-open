// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { MovePanel } from "./MovePanel";
import { button, click, type Rendered, render } from "./testing/render";

describe("moving the selected item", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  it("starts and stops moving, saying how while it lasts", () => {
    const asked: boolean[] = [];
    const panel = (moving: boolean) => (
      <MovePanel
        label="heater"
        moving={moving}
        movedBy={null}
        canUndo={false}
        onMoving={(on) => asked.push(on)}
        onUndo={() => undefined}
        onPutBack={() => undefined}
      />
    );
    shown = render(panel(false));
    const { container } = shown;

    expect(container.querySelector('[data-testid="move-offset"]')?.textContent).toBe(
      "The heater stands where its layout places it.",
    );
    expect(container.querySelector(".move-hint")).toBeNull();
    expect(button(container, "Move").getAttribute("aria-pressed")).toBe("false");
    // Nothing to undo or put back.
    expect(button(container, "Undo move").disabled).toBe(true);
    expect(button(container, "Put back").disabled).toBe(true);
    click(button(container, "Move"));

    shown.rerender(panel(true));
    expect(container.querySelector(".move-hint")?.textContent).toContain(
      "the heater moves as far as the pointer does, along the floor, in 10 cm steps",
    );
    click(button(container, "Done moving"));
    expect(asked).toEqual([true, false]);
  });

  it("says how far the item stands from its place, and takes it back", () => {
    const done: string[] = [];
    shown = render(
      <MovePanel
        label="temperature front"
        moving={false}
        movedBy={{ dx: -1, dy: 0.5 }}
        canUndo={true}
        onMoving={() => undefined}
        onUndo={() => done.push("undo")}
        onPutBack={() => done.push("put back")}
      />,
    );
    const { container } = shown;

    expect(container.querySelector('[data-testid="move-offset"]')?.textContent).toBe(
      "The temperature front stands −1.0 m along x and +0.5 m along y from where its layout places it.",
    );
    click(button(container, "Undo move"));
    click(button(container, "Put back"));
    expect(done).toEqual(["undo", "put back"]);
  });
});
