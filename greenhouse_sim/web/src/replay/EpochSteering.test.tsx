// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render, said } from "../testing/render";
import { ENDED_STEERING, EpochSteering, steeringText, WHAT_STEERING_DOES } from "./EpochSteering";

describe("a running epoch steered from its replay", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  it("says what a change does before one is made", () => {
    rendered = render(<EpochSteering waiting={false} taken={null} refusal={null} />);

    expect(said(rendered.container, "epoch-steering")).toContain(WHAT_STEERING_DOES);
    expect(WHAT_STEERING_DOES).toMatch(/not the one shown, and nothing forks/);
    expect(said(rendered.container, "epoch-steering-status")).toBe("");
  });

  it("says, once the run has ended, that a change now forks it", () => {
    rendered = render(
      <EpochSteering computing={false} waiting={false} taken={null} refusal="it ended first" />,
    );

    expect(said(rendered.container, "epoch-steering")).toContain(ENDED_STEERING);
    expect(said(rendered.container, "epoch-steering-refused")).toBe("Not changed: it ended first.");
    expect(
      rendered.container.querySelector('[data-testid="epoch-steering-refused"]')?.className,
    ).toBe("ds-notice ds-notice-problem targets-note");
  });

  it("says a change waits for the worker, then the moment the run took it from", () => {
    expect(steeringText({ waiting: true, taken: null })).toMatch(/waiting for its worker/);
    // A change on its way is the latest word, whatever an earlier one took.
    expect(steeringText({ waiting: true, taken: DAY_S })).toMatch(/waiting for its worker/);
    expect(steeringText({ waiting: false, taken: DAY_S + 6 * 3600 + 60 })).toBe(
      "The run took the latest change from Day 2, 06:01.",
    );
  });

  it("says why a change was refused, in the simulator's words, until the next is answered", () => {
    const reason =
      "epoch 0 of x is finished: it takes no more changes; a fork acts from a moment of it";
    rendered = render(<EpochSteering waiting={false} taken={60} refusal={reason} />);

    expect(said(rendered.container, "epoch-steering-refused")).toBe(`Not changed: ${reason}.`);
    expect(said(rendered.container, "epoch-steering-status")).toBe("");

    rendered.rerender(<EpochSteering waiting taken={60} refusal={reason} />);
    expect(rendered.container.querySelector('[data-testid="epoch-steering-refused"]')).toBeNull();
    expect(said(rendered.container, "epoch-steering-status")).toMatch(/waiting/);
  });
});
