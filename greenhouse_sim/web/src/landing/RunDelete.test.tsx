// @vitest-environment jsdom
import { createRef } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { button, click, type Rendered, render } from "../testing/render";
import { RunDelete } from "./RunDelete";

let shown: Rendered | undefined;
afterEach(() => {
  shown?.unmount();
  shown = undefined;
});

function drawn(computing: boolean): HTMLElement {
  shown = render(
    <RunDelete
      name="the run with seed 5"
      computing={computing}
      onDelete={async () => false}
      whenGone={createRef<HTMLElement>()}
    />,
  );
  return shown.container;
}

describe("a run's Delete", () => {
  it("is red at each step, and the answer that loses nothing is not", () => {
    const container = drawn(false);
    expect(button(container, "Delete the run with seed 5").classList).toContain("ds-button-danger");
    click(button(container, "Delete the run with seed 5"));
    expect(button(container, "Delete the run with seed 5").textContent).toBe(
      "Delete the run with seed 5",
    );
    expect(button(container, "Delete the run with seed 5").classList).toContain("ds-button-danger");
    expect(button(container, "Keep it").className).toBe("ds-button");
  });

  it("is red too when it stops the run first", () => {
    const container = drawn(true);
    expect(button(container, "Delete the run with seed 5").classList).toContain("ds-button-danger");
    click(button(container, "Delete the run with seed 5"));
    expect(button(container, "Stop and delete the run with seed 5").classList).toContain(
      "ds-button-danger",
    );
  });
});
