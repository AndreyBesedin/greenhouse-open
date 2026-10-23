// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { button, click, enter, type Rendered, render, said } from "../testing/render";
import { Findings } from "./Findings";
import type { Installation } from "./generated/assessedTypes";
import { HouseForm } from "./HouseForm";
import { RowCrops } from "./RowCrops";

const HOUSE = {
  installation_id: "house",
  name: "House",
  envelope: {},
  layout: { crop_rows: { rows: 3 } },
  row_crops: [{ row: 1, crop_model: "simple", variety: "cherry_tomato" }],
} as unknown as Installation;

function input(within: ParentNode, label: string): HTMLInputElement {
  const found = [...within.querySelectorAll("label")].find((each) => each.textContent === label);
  const control = found?.htmlFor ? within.querySelector(`[id="${found.htmlFor}"]`) : null;
  if (!(control instanceof HTMLInputElement)) {
    throw new Error(`no input labelled "${label}"`);
  }
  return control;
}

describe("the builder's parts (P12.2)", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  it("draft a house from the first form, its fields labelled as the schema titles them", () => {
    const onDraft = vi.fn();
    shown = render(<HouseForm busy={false} onDraft={onDraft} />);

    expect(input(shown.container, "Length (m)").value).toBe("12");
    enter(input(shown.container, "Crop rows"), "3");
    click(button(shown.container, "Draft this house"));

    expect(onDraft).toHaveBeenCalledOnce();
    expect(onDraft.mock.calls[0]?.[0]).toMatchObject({
      rows: 3,
      length_m: 12,
      crop_model: "simple",
    });
  });

  it("give one crop to the rows chosen, in one edit", () => {
    const onGive = vi.fn();
    shown = render(<RowCrops installation={HOUSE} onGive={onGive} />);
    const give = button(shown.container, "Give the chosen rows this crop");
    expect(give.disabled).toBe(true);

    const row = (n: number) =>
      shown?.container.querySelector<HTMLInputElement>(`[aria-label="Choose row ${n}"]`);
    click(row(2) as HTMLInputElement);
    click(row(3) as HTMLInputElement);
    const model = shown.container.querySelector<HTMLSelectElement>(".builder-give select");
    expect(model).not.toBeNull();
    enter(
      shown.container.querySelector<HTMLInputElement>(".builder-give input") as HTMLInputElement,
      "beefsteak",
    );
    click(give);

    expect(onGive).toHaveBeenCalledWith([2, 3], { crop_model: "simple", variety: "beefsteak" });
    // Every row chosen at once, and none again.
    const all = shown.container.querySelector<HTMLInputElement>('[aria-label="Choose every row"]');
    click(all as HTMLInputElement);
    expect([1, 2, 3].map((n) => row(n)?.checked)).toEqual([true, true, true]);
    click(all as HTMLInputElement);
    expect([1, 2, 3].map((n) => row(n)?.checked)).toEqual([false, false, false]);
  });

  it("say whether a draft runs, its errors first", () => {
    shown = render(
      <Findings
        assessment={{
          status: "assessed",
          findings: [
            { severity: "warning", code: "no_door", message: "No door.", items: [], rows: [] },
            {
              severity: "error",
              code: "unassigned_rows",
              message: "No crop chosen for rows 2.",
              items: [],
              rows: [2],
            },
          ],
        }}
      />,
    );

    expect(said(shown.container, "builder-runnable")).toBe("One error stops it running.");
    expect([...shown.container.querySelectorAll("li")].map((each) => each.dataset.code)).toEqual([
      "unassigned_rows",
      "no_door",
    ]);
    shown.rerender(<Findings assessment={{ status: "assessed", findings: [] }} />);
    expect(said(shown.container, "builder-runnable")).toBe("It can run.");
    // Until it is assessed, or if it cannot be, no findings of an edit before.
    shown.rerender(<Findings assessment={{ status: "asked" }} />);
    expect(said(shown.container, "builder-runnable")).toBe("Being assessed…");
    shown.rerender(<Findings assessment={{ status: "failed", problem: "the API answered 502" }} />);
    expect(said(shown.container, "builder-runnable")).toBe(
      "It cannot be assessed: the API answered 502",
    );
    expect(shown.container.querySelectorAll("li")).toHaveLength(0);
  });
});
