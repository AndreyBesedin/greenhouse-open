// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ScenarioSummary } from "../scenarios";
import {
  button,
  choose,
  click,
  enter,
  type Rendered,
  render,
  said,
  select,
} from "../testing/render";
import { CopyScenario } from "./CopyScenario";
import { Findings } from "./Findings";
import { FinishStep } from "./FinishStep";
import type { Installation } from "./generated/assessedTypes";
import { HouseForm } from "./HouseForm";
import { HouseIdentity } from "./HouseIdentity";
import { RowCrops } from "./RowCrops";
import { FIRST_RUN, RunStep } from "./RunStep";
import { keptAlready, whatStopsARun } from "./WhyNot";

const DIFFERENT_CROPS = "Rows grow different crops; a run grows one model and one variety.";

/** What describes a control: the text of each element its `aria-describedby`
 * names. */
function description(control: Element): string {
  return (control.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .filter((id) => id !== "")
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" ");
}

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

  it("ask for a seed beside the run step's button, as for its other fields", () => {
    shown = render(
      <RunStep
        weathers={["default"]}
        busy={false}
        reasons={[]}
        fields={{ ...FIRST_RUN, seed: "" }}
        onFields={vi.fn()}
        onRun={vi.fn()}
      />,
    );
    const form = shown.container.querySelector("form");

    // The browser says what is missing, at the field, and sends nothing.
    expect(form?.checkValidity()).toBe(false);
  });

  it("name each weather in words, and send it by its name", () => {
    const onFields = vi.fn();
    shown = render(
      <RunStep
        weathers={["default", "cold_spring_day"]}
        busy={false}
        reasons={[]}
        fields={FIRST_RUN}
        onFields={onFields}
        onRun={vi.fn()}
      />,
    );
    const weather = select(shown.container, "Weather");
    expect([...weather.options].map((option) => [option.value, option.text])).toEqual([
      ["default", "its own"],
      ["cold_spring_day", "cold spring day"],
    ]);
    choose(weather, "cold_spring_day");
    expect(onFields).toHaveBeenCalledWith({ ...FIRST_RUN, weather: "cold_spring_day" });
  });

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

  it("start the crop given from what the rows grow, so that a new variety keeps their model", () => {
    const onGive = vi.fn();
    const organ = {
      ...HOUSE,
      row_crops: [{ row: 1, crop_model: "organ", variety: "beefsteak" }],
    } as unknown as Installation;
    shown = render(<RowCrops installation={organ} onGive={onGive} />);
    const model = shown.container.querySelector<HTMLSelectElement>(".builder-give select");
    const variety = shown.container.querySelector<HTMLInputElement>(".builder-give input");
    expect([model?.value, variety?.value]).toEqual(["organ", "beefsteak"]);

    click(
      shown.container.querySelector<HTMLInputElement>('[aria-label="Choose row 2"]') as HTMLElement,
    );
    enter(variety as HTMLInputElement, "cherry_tomato");
    click(button(shown.container, "Give the chosen rows this crop"));

    expect(onGive).toHaveBeenCalledWith([2], { crop_model: "organ", variety: "cherry_tomato" });
  });

  it("offer every crop model the simulator grows", () => {
    shown = render(<RowCrops installation={HOUSE} onGive={vi.fn()} />);
    const options = shown.container.querySelectorAll<HTMLOptionElement>(
      ".builder-give select option",
    );

    expect([...options].map((each) => each.value)).toEqual([
      "simple",
      "organ",
      "reduced_tomgro",
      "vanthoor_katzin",
    ]);
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

  it("copy a scenario's house only under an identifier the simulator takes", () => {
    const scenario = { id: "climate_box", name: "Climate box" } as ScenarioSummary;
    const onCopy = vi.fn();
    shown = render(<CopyScenario scenarios={[scenario]} busy={false} onCopy={onCopy} />);
    const identifier = input(shown.container, "The copy's identifier");
    const copy = button(shown.container, "Copy its house");
    expect(identifier.value).toBe("climate_box_copy");

    enter(identifier, "my copy");
    expect(identifier.getAttribute("aria-invalid")).toBe("true");
    expect(copy.disabled).toBe(true);
    expect(shown.container.textContent).toContain("letters, digits, '_', '.' and '-' only");
    // The problem describes its field, and is drawn as one (`Field`, P19.9).
    const problem = document.getElementById(identifier.getAttribute("aria-describedby") ?? "");
    expect(problem?.textContent).toContain("letters, digits");
    expect(problem?.className).toBe("ds-field-problem");
    act(() => {
      shown?.container
        .querySelector("form")
        ?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    expect(onCopy).not.toHaveBeenCalled();

    enter(identifier, "my_copy");
    expect(identifier.hasAttribute("aria-invalid")).toBe(false);
    expect(identifier.hasAttribute("aria-describedby")).toBe(false);
    click(copy);
    expect(onCopy).toHaveBeenCalledExactlyOnceWith(scenario, "my_copy");
  });

  it("copy the scenario a runs dialog sent, once the scenarios are listed (P22.4)", () => {
    const box = { id: "climate_box", name: "Climate box" } as ScenarioSummary;
    const reference = { id: "reference_greenhouse", name: "Reference" } as ScenarioSummary;
    const onCopy = vi.fn();
    const copying = (scenarios: ScenarioSummary[]) => (
      <CopyScenario scenarios={scenarios} first={reference.id} busy={false} onCopy={onCopy} />
    );
    shown = render(copying([]));
    shown.rerender(copying([box, reference]));

    expect(input(shown.container, "The copy's identifier").value).toBe("reference_greenhouse_copy");
    click(button(shown.container, "Copy its house"));
    expect(onCopy).toHaveBeenCalledExactlyOnceWith(reference, "reference_greenhouse_copy");
  });
  it("say under the run step's button why it cannot run, each reason in full", () => {
    const run = (reasons: readonly string[], refused?: string) => (
      <RunStep
        weathers={["default"]}
        busy={false}
        reasons={reasons}
        refused={refused}
        fields={FIRST_RUN}
        onFields={vi.fn()}
        onRun={vi.fn()}
      />
    );
    shown = render(run([DIFFERENT_CROPS]));
    const runs = button(shown.container, "Run this revision");

    expect(runs.disabled).toBe(true);
    expect(said(shown.container, "builder-run-why")).toBe(`It cannot run: ${DIFFERENT_CROPS}`);
    // The reason is the button's description, read with it.
    expect(description(runs)).toBe(`It cannot run: ${DIFFERENT_CROPS}`);

    shown.rerender(run(["Save it first: a run is of a revision saved.", DIFFERENT_CROPS]));
    expect(
      [...shown.container.querySelectorAll(".builder-why li")].map((each) => each.textContent),
    ).toEqual(["Save it first: a run is of a revision saved.", DIFFERENT_CROPS]);

    // Nothing stops it: no reason, and the button undescribed.
    shown.rerender(run([], "the scenario my_greenhouse is registered already"));
    expect(button(shown.container, "Run this revision").disabled).toBe(false);
    expect(shown.container.querySelector(".builder-why")).toBeNull();
    expect(button(shown.container, "Run this revision").hasAttribute("aria-describedby")).toBe(
      false,
    );
    // What the simulator refused of the last run asked for, said at once.
    const refused = shown.container.querySelector('[data-testid="builder-run-refused"]');
    expect(refused?.getAttribute("role")).toBe("alert");
    expect(refused?.textContent).toBe(
      "It does not run: the scenario my_greenhouse is registered already",
    );
  });

  it("say under the finishing buttons why each cannot be used, a reason both share once", () => {
    const taken = keptAlready("my_greenhouse");
    shown = render(
      <FinishStep
        busy={false}
        goBackReasons={[taken]}
        startReasons={[taken, DIFFERENT_CROPS]}
        refused="It is not saved: draft 'my_greenhouse' is at revision 2, not 1: another was saved since"
        onGoBack={vi.fn()}
        onStartRun={vi.fn()}
      />,
    );
    const goBack = button(shown.container, "Save and go back");
    const start = button(shown.container, "Save and start a run");

    expect([goBack.disabled, start.disabled]).toEqual([true, true]);
    expect(said(shown.container, "builder-finish-save-why")).toBe(`It cannot be saved: ${taken}`);
    expect(said(shown.container, "builder-finish-start-why")).toBe(
      `A run cannot be started: ${DIFFERENT_CROPS}`,
    );
    expect(description(goBack)).toBe(`It cannot be saved: ${taken}`);
    expect(description(start)).toBe(
      `It cannot be saved: ${taken} A run cannot be started: ${DIFFERENT_CROPS}`,
    );
    expect(said(shown.container, "builder-finish-refused")).toContain("another was saved since");
  });

  it("say what stops a run in the simulator's words: each error, or why there are none yet", () => {
    expect(
      whatStopsARun({
        status: "assessed",
        findings: [
          { severity: "warning", code: "no_door", message: "No door.", items: [], rows: [] },
          {
            severity: "error",
            code: "mixed_crops",
            message: DIFFERENT_CROPS,
            items: [],
            rows: [1, 2],
          },
        ],
      }),
    ).toEqual([DIFFERENT_CROPS]);
    expect(whatStopsARun({ status: "assessed", findings: [] })).toEqual([]);
    expect(whatStopsARun({ status: "asked" })).toEqual(["It is not assessed yet."]);
    expect(whatStopsARun({ status: "failed", problem: "the API answered 502" })).toEqual([
      "It cannot be assessed: the API answered 502",
    ]);
  });

  it("refuse a first draft under a kept draft's identifier, saying so at the field and the button", () => {
    const onDraft = vi.fn();
    shown = render(<HouseForm busy={false} kept={["my_greenhouse"]} onDraft={onDraft} />);
    const identifier = input(shown.container, "Identifier");
    const draft = button(shown.container, "Draft this house");

    expect(identifier.value).toBe("my_greenhouse");
    expect(identifier.getAttribute("aria-invalid")).toBe("true");
    expect(description(identifier)).toBe(keptAlready("my_greenhouse"));
    expect(draft.disabled).toBe(true);
    expect(description(draft)).toBe(`It cannot be drafted: ${keptAlready("my_greenhouse")}`);

    enter(identifier, "my_greenhouse_2");
    expect(identifier.hasAttribute("aria-invalid")).toBe(false);
    click(button(shown.container, "Draft this house"));
    expect(onDraft).toHaveBeenCalledOnce();
  });

  it("say at each field what the simulator refused of the first form's values, until it is changed", () => {
    const onDraft = vi.fn();
    const form = (problems: { field: string; message: string }[], refused?: string) => (
      <HouseForm busy={false} problems={problems} refused={refused} onDraft={onDraft} />
    );
    shown = render(form([]));
    click(button(shown.container, "Draft this house"));
    shown.rerender(
      form(
        [{ field: "spans", message: "Input should be greater than 0" }],
        "not the first form's values: spans: Input should be greater than 0",
      ),
    );
    const spans = input(shown.container, "Spans");

    expect(spans.getAttribute("aria-invalid")).toBe("true");
    expect(description(spans)).toBe("Input should be greater than 0");
    expect(said(shown.container, "builder-draft-refused")).toBe(
      "The house cannot be drafted: not the first form's values: spans: Input should be greater than 0",
    );
    // Changed, the field is no longer what was refused.
    enter(spans, "3");
    expect(input(shown.container, "Spans").hasAttribute("aria-invalid")).toBe(false);
  });

  it("copy a scenario's house only under an identifier no kept draft has", () => {
    const scenario = { id: "climate_box", name: "Climate box" } as ScenarioSummary;
    shown = render(
      <CopyScenario
        scenarios={[scenario]}
        busy={false}
        kept={["climate_box_copy"]}
        onCopy={vi.fn()}
      />,
    );
    const identifier = input(shown.container, "The copy's identifier");

    expect(button(shown.container, "Copy its house").disabled).toBe(true);
    expect(description(identifier)).toBe(keptAlready("climate_box_copy"));
    enter(identifier, "climate_box_copy_2");
    expect(button(shown.container, "Copy its house").disabled).toBe(false);
  });

  it("say at the identity's identifier field that a kept draft has it, until another is typed", () => {
    const taken = keptAlready("my_greenhouse");
    shown = render(
      <HouseIdentity
        draftId="my_greenhouse"
        name="My greenhouse"
        taken={taken}
        onRename={vi.fn()}
      />,
    );
    const identifier = input(shown.container, "Identifier");

    expect(description(identifier)).toBe(taken);
    enter(identifier, "my_greenhouse_2");
    expect(input(shown.container, "Identifier").hasAttribute("aria-invalid")).toBe(false);
  });
});
