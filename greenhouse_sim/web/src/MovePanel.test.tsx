// @vitest-environment jsdom
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

  it("says up front that its moves make a new run, lists them, and applies or cancels them", () => {
    const done: string[] = [];
    shown = render(panel(DRAFT, done));
    const { container } = shown;

    expect(container.querySelector('[data-testid="move-new-run"]')?.textContent).toBe(
      "Moving equipment changes the house's climate, so it is a new run: applying these moves starts it from its first day.",
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
    click(button(container, "Start a new run with these moves"));
    click(button(container, "Cancel"));
    expect(done).toEqual(["put back co2", "put everything back", "apply", "cancel"]);
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
      "The run played back starts over with them, and the view follows it.",
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
