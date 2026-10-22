// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { type MoveDraft, MovePanel } from "./MovePanel";
import { button, click, type Rendered, render } from "./testing/render";

// A session that moves the heater and a sensor, not yet applied.
const DRAFT: MoveDraft = {
  moves: [
    { item: "heater", label: "heater", by: { dx: -1, dy: 0.5 } },
    { item: "co2", label: "CO2 sensor", by: { dx: 0.3, dy: 0 } },
  ],
  changed: true,
  following: false,
  applying: false,
  failure: null,
};

describe("moving equipment and sensors", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  function panel(draft: MoveDraft | null, done: string[] = []) {
    return (
      <MovePanel
        item={{ label: "heater", movedBy: draft === null ? null : { dx: -1, dy: 0.5 } }}
        draft={draft}
        onMove={() => done.push("move")}
        onPutBack={(item) => done.push(`put back ${item}`)}
        onPutEverythingBack={() => done.push("put everything back")}
        onApply={() => done.push("apply")}
        onCancel={() => done.push("cancel")}
      />
    );
  }

  it("says where the item stands, and starts a session", () => {
    const done: string[] = [];
    shown = render(panel(null, done));
    const { container } = shown;

    expect(container.querySelector('[data-testid="move-offset"]')?.textContent).toBe(
      "The heater stands where its layout places it.",
    );
    // Nothing is said of a new run before moving starts.
    expect(container.querySelector('[data-testid="move-new-run"]')).toBeNull();
    click(button(container, "Move"));
    expect(done).toEqual(["move"]);
  });

  it("says in a line what its moves do, the rest folded, lists them, and puts them back or cancels them", () => {
    const done: string[] = [];
    shown = render(panel(DRAFT, done));
    const { container } = shown;

    expect(container.querySelector('[data-testid="move-new-run"]')?.textContent).toBe(
      "Drag equipment or a sensor in the view to move it. Applying the moves starts the run again from its first day.",
    );
    const details = container.querySelector<HTMLDetailsElement>(".move-details");
    expect(details?.open).toBe(false);
    expect(details?.querySelector("summary")?.textContent).toBe("How moving works");
    expect(details?.querySelector(".move-hint")?.textContent).toContain(
      "the moves make a new run, which keeps the heating targets changed in the run.",
    );
    expect(container.querySelector('[data-testid="move-offset"]')?.textContent).toBe(
      "The heater stands −1.0 m along x and +0.5 m along y from where its layout places it.",
    );
    const listed = [...container.querySelectorAll('[data-testid="move-list"] li')].map(
      (item) => item.textContent,
    );
    expect(listed).toEqual([
      "heater: −1.0 m along x and +0.5 m along y Put back",
      "CO2 sensor: +0.3 m along x and 0.0 m along y Put back",
    ]);
    // Moving has started: the session's buttons, not Move.
    expect([...container.querySelectorAll("button")].map((each) => each.textContent)).not.toContain(
      "Move",
    );
    click(button(container, "Put the CO2 sensor back"));
    click(button(container, "Put everything back"));
    click(button(container, "Cancel"));
    expect(done).toEqual(["put back co2", "put everything back", "cancel"]);
  });

  it("asks before its moves start a new run: confirmed, it applies them; taken back, they stay", () => {
    const done: string[] = [];
    shown = render(panel(DRAFT, done));
    const { container } = shown;
    const startIt = button(container, "Start a new run with these moves");

    click(startIt);
    // Asked, not applied, the question taking the keyboard's focus.
    expect(done).toEqual([]);
    expect(container.querySelector('[data-testid="move-confirm"]')?.textContent).toBe(
      "The run starts again from its first day with these moves; the moment reached is left behind.",
    );
    expect(container.querySelector(".move-confirm legend")?.textContent).toBe("Start a new run?");
    expect(document.activeElement).toBe(button(container, "Start the new run"));
    expect(container.querySelector('[data-testid="move-list"]')).not.toBeNull();

    click(button(container, "Back to the moves"));
    expect(done).toEqual([]);
    expect(container.querySelector('[data-testid="move-confirm"]')).toBeNull();
    expect(document.activeElement).toBe(button(container, "Start a new run with these moves"));

    click(button(container, "Start a new run with these moves"));
    click(button(container, "Start the new run"));
    expect(done).toEqual(["apply"]);
    expect(container.querySelector('[data-testid="move-confirm"]')).toBeNull();
  });

  it("goes back to the moves on Escape in the question, which the session's own Escape then leaves alone", () => {
    const done: string[] = [];
    shown = render(panel(DRAFT, done));
    const { container } = shown;
    click(button(container, "Start a new run with these moves"));
    const pressed = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });

    act(() => {
      button(container, "Start the new run").dispatchEvent(pressed);
    });

    // Handled here: the view's Escape, which cancels the moves, sees it done.
    expect(pressed.defaultPrevented).toBe(true);
    expect(container.querySelector('[data-testid="move-confirm"]')).toBeNull();
    expect(done).toEqual([]);
  });

  it("applies nothing that changes nothing, and puts back nothing that is not moved", () => {
    shown = render(panel({ ...DRAFT, moves: [], changed: false }));
    const { container } = shown;

    expect(container.querySelector('[data-testid="move-list"]')?.textContent).toBe(
      "Everything stands where its layout places it.",
    );
    expect(button(container, "Start a new run with these moves").disabled).toBe(true);
    expect(button(container, "Put everything back").disabled).toBe(true);
    expect(button(container, "Cancel").disabled).toBe(false);
  });

  it("says, following the run played back, that it starts over with the moves, and why it could not", () => {
    shown = render(panel({ ...DRAFT, following: true }));
    const { container } = shown;

    expect(container.querySelector('[data-testid="move-new-run"]')?.textContent).toContain(
      "Applying the moves starts the run played back again from its first day, and the view follows it.",
    );
    click(button(container, "Start a new run with these moves"));
    expect(container.querySelector('[data-testid="move-confirm"]')?.textContent).toMatch(
      /^The run played back starts again from its first day/,
    );
    shown.rerender(panel({ ...DRAFT, following: true, applying: true }));
    expect(button(container, "Starting the new run…").disabled).toBe(true);
    expect(button(container, "Cancel").disabled).toBe(true);
    expect(button(container, "Put the heater back").disabled).toBe(true);

    shown.rerender(panel({ ...DRAFT, following: true, failure: "the simulator answered 400" }));
    expect(container.querySelector('[data-testid="move-failure"]')?.textContent).toBe(
      "The run played back could not start over: the simulator answered 400.",
    );
    expect(button(container, "Start a new run with these moves").disabled).toBe(false);
  });
});
