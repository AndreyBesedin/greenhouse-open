// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { type Rendered, render } from "../testing/render";
import { Notice } from "./Notice";
import { StatusChip } from "./StatusChip";

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

describe("StatusChip", () => {
  it("says its status in words, drawn in its tone, plain unless it says otherwise", () => {
    expect(drawn(<StatusChip>Finished</StatusChip>).outerHTML).toBe(
      '<span class="ds-status-chip">Finished</span>',
    );
    expect(drawn(<StatusChip tone="active">Running</StatusChip>).className).toBe(
      "ds-status-chip ds-status-chip-active",
    );
    expect(
      drawn(
        <StatusChip tone="problem" className="landing-status">
          Failed
        </StatusChip>,
      ).className,
    ).toBe("ds-status-chip ds-status-chip-problem landing-status");
  });

  it("shows its note on hover, and says it to whoever hears the page", () => {
    const element = drawn(
      <StatusChip tone="problem" note="Files of this run are missing.">
        Damaged
      </StatusChip>,
    );
    expect(element.title).toBe("Files of this run are missing.");
    expect(element.textContent).toBe("Damaged Files of this run are missing.");
    expect(element.querySelector(".visually-hidden")?.textContent).toBe(
      " Files of this run are missing.",
    );
  });

  it("needs its words, as one string, so that a colour never says a status alone", () => {
    // @ts-expect-error a chip with no words is a colour alone
    drawn(<StatusChip tone="problem" />);
    drawn(
      // @ts-expect-error its words are a string, not what draws them
      <StatusChip>
        <strong>Failed</strong>
      </StatusChip>,
    );
  });
});

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
