// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useFolds } from "../folds";
import { type Rendered, render } from "../testing/render";
import { Fold } from "./Fold";

let shown: Rendered | undefined;
afterEach(() => {
  shown?.unmount();
  shown = undefined;
});

function Folds({ onToggled }: { onToggled: (open: boolean) => void }) {
  const fold = useFolds<"open" | "folded">(["open"]);
  const { open, onToggle } = fold("folded");
  return (
    <>
      <Fold summary="Shown" {...fold("open")}>
        what it holds
      </Fold>
      <Fold
        summary="Folded"
        className="panel-fold"
        open={open}
        onToggle={(event) => {
          onToggle(event);
          onToggled(event.currentTarget.open);
        }}
      >
        what it holds, folded
      </Fold>
    </>
  );
}

describe("Fold", () => {
  it("is the browser's details, opened or folded as its state says, by its line", () => {
    const toggled = vi.fn();
    shown = render(<Folds onToggled={toggled} />);
    const [shownFold, folded] = [...shown.container.querySelectorAll("details")];
    expect(shownFold?.open).toBe(true);
    expect(shownFold?.className).toBe("ds-fold");
    expect(shownFold?.querySelector(":scope > summary")?.textContent).toBe("Shown");
    expect(folded?.open).toBe(false);
    expect(folded?.className).toBe("ds-fold panel-fold");

    // Opened as a person opens it, its state keeps it open when drawn again.
    act(() => {
      (folded as HTMLDetailsElement).open = true;
      folded?.dispatchEvent(new Event("toggle"));
    });
    expect(toggled).toHaveBeenCalledWith(true);
    shown.rerender(<Folds onToggled={toggled} />);
    expect(shown.container.querySelectorAll("details")[1]?.open).toBe(true);
  });
});
