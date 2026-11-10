import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GithubMark, HomeIcon, PencilIcon, SearchIcon } from "./index";

describe("the viewer's icons", () => {
  it.each([
    ["GithubMark", GithubMark],
    ["HomeIcon", HomeIcon],
    ["PencilIcon", PencilIcon],
    ["SearchIcon", SearchIcon],
  ])("%s is decoration, drawn in the text's colour", (_name, Drawn) => {
    const html = renderToStaticMarkup(<Drawn />);
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain('focusable="false"');
    expect(html).toMatch(/(fill|stroke)="currentColor"/);
  });
});
