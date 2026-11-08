// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { type Rendered, render } from "../testing/render";
import { Field } from "./Field";

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
