// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useFolds } from "../folds";
import { type Rendered, render } from "../testing/render";
import { Field } from "./Field";
import { Fold } from "./Fold";

let shown: Rendered | undefined;
afterEach(() => {
  shown?.unmount();
  shown = undefined;
});

/** The text of the elements `ids` names, space separated, in order. */
function textOf(ids: string | null): string[] {
  return (ids ?? "")
    .split(" ")
    .filter((id) => id !== "")
    .map((id) => document.getElementById(id)?.textContent ?? `no #${id}`);
}

describe("Field", () => {
  it("names its control by its label, which stands beside it", () => {
    shown = render(<Field label="Seed">{(control) => <input {...control} />}</Field>);
    const input = shown.container.querySelector("input") as HTMLInputElement;
    const label = shown.container.querySelector("label") as HTMLLabelElement;
    expect(label.textContent).toBe("Seed");
    expect(label.htmlFor).toBe(input.id);
    expect([...(input.labels ?? [])].map((each) => each.textContent)).toEqual(["Seed"]);
    expect(input.hasAttribute("aria-describedby")).toBe(false);
    expect(input.hasAttribute("aria-invalid")).toBe(false);
    expect(shown.container.firstElementChild?.className).toBe("ds-field");
  });

  it("is described by its hint and its problem, which are not part of its name", () => {
    shown = render(
      <Field label="Seed" hint="Digits only." problem="Not a number." className="landing-seed">
        {(control) => <input {...control} />}
      </Field>,
    );
    const input = shown.container.querySelector("input") as HTMLInputElement;
    expect(textOf(input.getAttribute("aria-describedby"))).toEqual([
      "Digits only.",
      "Not a number.",
    ]);
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect([...(input.labels ?? [])].map((each) => each.textContent)).toEqual(["Seed"]);
    expect(shown.container.firstElementChild?.className).toBe("ds-field landing-seed");
  });

  it("is invalid only with a problem", () => {
    shown = render(
      <Field label="Seed" hint="Digits only.">
        {(control) => <input {...control} />}
      </Field>,
    );
    const input = shown.container.querySelector("input") as HTMLInputElement;
    expect(textOf(input.getAttribute("aria-describedby"))).toEqual(["Digits only."]);
    expect(input.hasAttribute("aria-invalid")).toBe(false);
  });

  it("gives each field its own control's id", () => {
    shown = render(
      <>
        <Field label="Seed">{(control) => <input {...control} />}</Field>
        <Field label="Pace">{(control) => <select {...control} />}</Field>
      </>,
    );
    const [seed, pace] = [...shown.container.querySelectorAll("input, select")];
    expect(seed?.id).not.toBe(pace?.id);
    expect((pace as HTMLSelectElement).labels?.[0]?.textContent).toBe("Pace");
  });

  it("needs its label", () => {
    shown = render(
      // @ts-expect-error a control with no label has no name
      <Field>{(control) => <input {...control} />}</Field>,
    );
  });
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
