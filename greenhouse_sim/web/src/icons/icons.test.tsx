import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  GithubMark,
  HomeIcon,
  PauseIcon,
  PencilIcon,
  PlayIcon,
  SearchIcon,
  StepBackIcon,
  StepForwardIcon,
} from "./index";

describe("the viewer's icons", () => {
  it.each([
    ["GithubMark", GithubMark],
    ["HomeIcon", HomeIcon],
    ["PauseIcon", PauseIcon],
    ["PencilIcon", PencilIcon],
    ["PlayIcon", PlayIcon],
    ["SearchIcon", SearchIcon],
    ["StepBackIcon", StepBackIcon],
    ["StepForwardIcon", StepForwardIcon],
  ])("%s is decoration, drawn in the text's colour", (_name, Drawn) => {
    const html = renderToStaticMarkup(<Drawn />);
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain('focusable="false"');
    expect(html).toMatch(/(fill|stroke)="currentColor"/);
  });

  it("are drawn at their size, or at the one asked for", () => {
    expect(renderToStaticMarkup(<StepBackIcon />)).toContain('width="18" height="18"');
    expect(renderToStaticMarkup(<PlayIcon size={20} />)).toContain('width="20" height="20"');
  });
});
