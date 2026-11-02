// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { type Rendered, render } from "../testing/render";
import { HomeButton } from "./HomeButton";
import { LANDING_PATH } from "./paths";

describe("the way home", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  it("is a link to the landing page, named Home", () => {
    rendered = render(<HomeButton />);
    const link = rendered.container.querySelector("a");

    expect(link?.getAttribute("href")).toBe(LANDING_PATH);
    expect(link?.textContent?.trim()).toBe("Home");
  });

  it("hides its icon from whoever hears the page, so that it is named once", () => {
    rendered = render(<HomeButton />);

    expect(rendered.container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});
