// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomeIcon } from "../icons";
import { button, click, type Rendered, render } from "../testing/render";
import { Button } from "./Button";
import { buttonClass } from "./buttonClass";
import { IconButton } from "./IconButton";
import { LinkButton } from "./LinkButton";

let shown: Rendered | undefined;
afterEach(() => {
  shown?.unmount();
  shown = undefined;
});

/** Draws `element`, and gives what it draws. */
function drawn(element: React.ReactNode): HTMLElement {
  shown = render(element);
  return shown.container.firstElementChild as HTMLElement;
}

describe("what is drawn as a button", () => {
  it("is a plain target unless it says otherwise, with a page's own class last", () => {
    expect(buttonClass({})).toBe("ds-button");
    expect(buttonClass({ tone: "primary" })).toBe("ds-button ds-button-primary");
    expect(buttonClass({ tone: "danger", size: "compact" }, "landing-go")).toBe(
      "ds-button ds-button-danger ds-button-compact landing-go",
    );
  });
});

describe("Button", () => {
  it("is the browser's button, in the tab order, named by its words", () => {
    const element = drawn(<Button>Save</Button>);
    expect(element.tagName).toBe("BUTTON");
    expect(element.tabIndex).toBe(0);
    expect(element.textContent).toBe("Save");
  });

  it("submits no form unless asked to", () => {
    const submitted = vi.fn((event: React.FormEvent) => event.preventDefault());
    shown = render(
      <form onSubmit={submitted}>
        <Button>Check</Button>
        <Button type="submit">Send</Button>
      </form>,
    );
    click(button(shown.container, "Check"));
    expect(submitted).not.toHaveBeenCalled();
    click(button(shown.container, "Send"));
    expect(submitted).toHaveBeenCalledOnce();
  });

  it("when disabled, cannot be pressed, nor take the focus", () => {
    const pressed = vi.fn();
    shown = render(
      <Button disabled onClick={pressed}>
        Save
      </Button>,
    );
    const element = button(shown.container, "Save");
    expect(element.disabled).toBe(true);
    click(element);
    expect(pressed).not.toHaveBeenCalled();
    element.focus();
    expect(document.activeElement).not.toBe(element);
  });

  it("when enabled, is pressed, and takes the focus", () => {
    const pressed = vi.fn();
    shown = render(<Button onClick={pressed}>Save</Button>);
    const element = button(shown.container, "Save");
    click(element);
    expect(pressed).toHaveBeenCalledOnce();
    element.focus();
    expect(document.activeElement).toBe(element);
  });

  it("needs its words", () => {
    // @ts-expect-error a button with no words has no name; `IconButton` takes a label
    expect(drawn(<Button />).textContent).toBe("");
  });
});

describe("LinkButton", () => {
  it("is a link, in the tab order, drawn as a button", () => {
    const element = drawn(
      <LinkButton href="/builder" tone="primary" className="landing-go">
        Build
      </LinkButton>,
    ) as HTMLAnchorElement;
    expect(element.tagName).toBe("A");
    expect(element.getAttribute("href")).toBe("/builder");
    expect(element.tabIndex).toBe(0);
    expect(element.className).toBe("ds-button ds-button-primary landing-go");
  });

  it("needs somewhere to go and its words, and has no disabled", () => {
    // @ts-expect-error an `<a>` without a place to go is no link
    drawn(<LinkButton>Build</LinkButton>);
    shown?.unmount();
    // @ts-expect-error a link with no words has no name
    drawn(<LinkButton href="/builder" />);
    shown?.unmount();
    shown = render(
      // @ts-expect-error a link cannot be disabled
      <LinkButton href="/builder" disabled>
        Build
      </LinkButton>,
    );
  });
});

describe("IconButton", () => {
  it("is named by its label, its icon staying decoration", () => {
    const element = drawn(
      <IconButton label="Home">
        <HomeIcon />
      </IconButton>,
    );
    expect(element.tagName).toBe("BUTTON");
    expect(element.getAttribute("aria-label")).toBe("Home");
    expect(element.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(element.textContent).toBe("");
  });

  it("takes a button's tone, size, state and a page's class", () => {
    const pressed = vi.fn();
    const element = drawn(
      <IconButton
        label="Home"
        tone="danger"
        size="compact"
        className="replay-go"
        disabled
        onClick={pressed}
      >
        <HomeIcon />
      </IconButton>,
    ) as HTMLButtonElement;
    expect(element.className).toBe(
      "ds-button ds-button-danger ds-button-compact ds-icon-button replay-go",
    );
    click(element);
    expect(pressed).not.toHaveBeenCalled();
    expect(element.disabled).toBe(true);
  });

  it("needs its label, which nothing passed through can take the place of", () => {
    drawn(
      // @ts-expect-error an icon alone names nothing
      <IconButton>
        <HomeIcon />
      </IconButton>,
    );
    shown?.unmount();
    // TypeScript lets a hyphenated attribute through, so that it is refused here.
    const element = drawn(
      <IconButton label="Home" aria-label="Something else">
        <HomeIcon />
      </IconButton>,
    );
    expect(element.getAttribute("aria-label")).toBe("Home");
    shown?.unmount();
    // A reference to another element would win over the label, in a browser.
    shown = render(
      <>
        <span id="other">Something else</span>
        <IconButton label="Home" aria-labelledby="other">
          <HomeIcon />
        </IconButton>
      </>,
    );
    expect(button(shown.container, "Home").hasAttribute("aria-labelledby")).toBe(false);
  });
});
