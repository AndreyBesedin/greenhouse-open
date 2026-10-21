// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { useFolds } from "./folds";
import { type Rendered, render } from "./testing/render";

function Sections() {
  const fold = useFolds<"moment" | "house">(["moment"]);
  return (
    <>
      <details className="moment" {...fold("moment")}>
        <summary>moment</summary>
      </details>
      <details className="house" {...fold("house")}>
        <summary>house</summary>
      </details>
    </>
  );
}

describe("panels folded to their line", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  it("start folded but for those named open (#273)", () => {
    shown = render(<Sections />);
    const { container } = shown;

    expect(container.querySelector("details.moment")?.hasAttribute("open")).toBe(true);
    expect(container.querySelector("details.house")?.hasAttribute("open")).toBe(false);
  });
});
