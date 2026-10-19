// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { SourceChooser } from "./SourceChooser";
import type { ScenarioSummary, ScenariosState } from "./scenarios";
import { button, click, enter, type Rendered, render, said } from "./testing/render";

const REFERENCE: ScenarioSummary = {
  id: "reference_greenhouse",
  name: "Reference greenhouse",
  description: "The reference scenario: 32 tomato plants in a small three-span house",
  plants: 32,
  duration_days: 120,
  layouts: ["default"],
  opening_day: 80,
};
const BOX: ScenarioSummary = {
  id: "climate_box",
  name: "Climate box",
  description: "A sealed box with a heater and two fans",
  plants: 32,
  duration_days: 14,
  layouts: ["default"],
};
const SCENARIOS: ScenariosState = { status: "loaded", scenarios: [REFERENCE, BOX] };
const DAY_S = 86_400;
const NOON_S = 43_200;

describe("the choice of what the viewer shows", () => {
  let chooser: Rendered | undefined;
  afterEach(() => chooser?.unmount());

  function shown(onSource = vi.fn(), initiallyOpen = false) {
    chooser = render(
      <SourceChooser
        scenarios={SCENARIOS}
        source={{ kind: "example" }}
        scene={{ status: "none" }}
        initiallyOpen={initiallyOpen}
        onSource={onSource}
      />,
    );
    const details = chooser.container.querySelector("details");
    if (details === null) {
      throw new Error("no chooser");
    }
    return { details, onSource };
  }

  it("is folded to the line that says what is shown, unless nothing is chosen yet", () => {
    const { details } = shown();

    expect(details.open).toBe(false);
    expect(said(details, "scene-status")).toBe("Showing the example scene.");
    chooser?.unmount();
    expect(shown(vi.fn(), true).details.open).toBe(true);
  });

  it("puts the scenarios, the test scenes and the plant lab apart, each saying what it is", () => {
    const { details } = shown();
    const groups = [...details.querySelectorAll("section")].map((group) =>
      group.getAttribute("aria-label"),
    );

    expect(groups).toEqual(["Scenarios", "Test scenes", "Plant lab"]);
    expect(details.querySelector("caption")?.textContent).toBe("Scenarios");
    expect(details.textContent).toContain("Greenhouses the simulator runs through days");
    expect(details.textContent).toContain("Drawn without a run, to check the renderer.");
    // The grid and cube the viewer draws is no longer called a reference.
    expect(button(details, "Empty grid")).toBeDefined();
    // Each scenario is described under its name.
    expect(details.querySelector(".scenario-description")?.textContent).toBe(REFERENCE.description);
  });

  it("opens a scenario on its opening day, or plays it live, and folds once chosen", () => {
    const { details, onSource } = shown(vi.fn(), true);

    click(button(details, "Open reference_greenhouse"));
    expect(onSource).toHaveBeenLastCalledWith({
      kind: "scenario",
      scenarioId: "reference_greenhouse",
      field: "climate",
      time: 80 * DAY_S + NOON_S,
    });
    expect(details.open).toBe(false);

    click(button(details, "Play climate_box live"));
    expect(onSource).toHaveBeenLastCalledWith({ kind: "live", scenarioId: "climate_box" });
  });

  it("chooses a test scene or the plant lab by name", () => {
    const { details, onSource } = shown();

    click(button(details, "Empty grid"));
    expect(onSource).toHaveBeenLastCalledWith({ kind: "reference" });
    click(button(details, "Plant lab"));
    expect(onSource).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "plants" }));
  });

  it("filters every choice by name, identifier or description", () => {
    const { details } = shown(vi.fn(), true);
    const filter = details.querySelector<HTMLInputElement>('input[type="search"]');
    if (filter === null) {
      throw new Error("no filter");
    }
    const names = () =>
      [...details.querySelectorAll(".scenario-name, .chooser-choices button")].map(
        (each) => each.textContent,
      );

    enter(filter, "HEATER");
    expect(names()).toEqual(["Climate box"]);
    enter(filter, "reference_");
    expect(names()).toEqual(["Reference greenhouse"]);
    enter(filter, "gallery");
    expect(names()).toEqual(["Fixture gallery"]);
    expect(details.textContent).toContain("No scenario matches “gallery”.");
    enter(filter, "");
    expect(names()).toHaveLength(7);
  });
});
