// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { type Rendered, render } from "../testing/render";
import { Notice } from "./Notice";

let shown: Rendered | undefined;
afterEach(() => {
  shown?.unmount();
  shown = undefined;
});

/** Draws `element`, and gives what it draws. */
function drawn(element: React.ReactNode): HTMLElement {
  shown?.unmount();
  shown = render(element);
  return shown.container.firstElementChild as HTMLElement;
}

describe("Notice", () => {
  it("is an alert when it says a problem, and a status otherwise", () => {
    const problem = drawn(<Notice kind="problem">Not started: no worker is free.</Notice>);
    expect(problem.tagName).toBe("P");
    expect(problem.getAttribute("role")).toBe("alert");
    expect(problem.className).toBe("ds-notice ds-notice-problem");
    expect(problem.textContent).toBe("Not started: no worker is free.");

    const status = drawn(
      <Notice kind="status" className="landing-note">
        Saved.
      </Notice>,
    );
    expect(status.getAttribute("role")).toBe("status");
    expect(status.className).toBe("ds-notice ds-notice-status landing-note");
  });

  it("needs its kind and what it says", () => {
    // @ts-expect-error a notice's kind sets its role
    drawn(<Notice>Saved.</Notice>);
    // @ts-expect-error a notice with nothing to say is a colour alone
    drawn(<Notice kind="status" />);
  });
});
