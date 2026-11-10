// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ScenarioSummary } from "../scenarios";
import { enter, type Rendered, render } from "../testing/render";
import { ScenarioCombobox, scrolledTo } from "./ScenarioCombobox";

function scenario(id: string, name: string, description: string): ScenarioSummary {
  return { id, name, description, plants: 4, duration_days: 120, layouts: ["default"] };
}

const SCENARIOS = [
  scenario("reference_greenhouse", "Reference greenhouse", "organ-level tomato crop"),
  scenario("tomgro_house", "TOMGRO house", "crop grown by area"),
  scenario("sensor_lab", "Sensor lab", "sensors and their errors"),
];
const COUNTS = new Map([
  ["reference_greenhouse", 4],
  ["tomgro_house", 1],
]);

describe("the choice of a scenario to open", () => {
  let drawn: Rendered | undefined;
  afterEach(() => drawn?.unmount());

  function shown(counts: ReadonlyMap<string, number> | null = COUNTS) {
    const onChoose = vi.fn();
    const onBuild = vi.fn();
    const rendered = render(
      <ScenarioCombobox
        scenarios={SCENARIOS}
        counts={counts}
        onChoose={onChoose}
        onBuild={onBuild}
      />,
    );
    drawn = rendered;
    const input = rendered.container.querySelector("input");
    if (input === null) {
      throw new Error("no search box");
    }
    const options = () => [...rendered.container.querySelectorAll('[role="option"]')];
    const press = (key: string) =>
      act(() => {
        input.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
      });
    const pointOn = (option: Element | undefined) =>
      act(() => {
        option?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      });
    return { input, options, press, pointOn, onChoose, onBuild };
  }

  it("lists every scenario with its runs, and a way to build one, once it is in focus", () => {
    const { input, options } = shown();
    expect(input.getAttribute("role")).toBe("combobox");
    expect(input.getAttribute("aria-expanded")).toBe("false");
    expect(options()).toHaveLength(0);

    act(() => input.focus());

    expect(input.getAttribute("aria-expanded")).toBe("true");
    expect(options().map((option) => option.textContent)).toEqual([
      "Reference greenhouse4 runsreference_greenhouse · organ-level tomato crop",
      "TOMGRO house1 runtomgro_house · crop grown by area",
      "Sensor labno runssensor_lab · sensors and their errors",
      "Build a new scenario",
    ]);
  });

  it("stays shut when a dialog it opened gives it focus back, and opens when asked", () => {
    const rendered = render(
      <ScenarioCombobox
        scenarios={SCENARIOS}
        counts={COUNTS}
        behindDialog
        onChoose={vi.fn()}
        onBuild={vi.fn()}
      />,
    );
    drawn = rendered;
    const input = rendered.container.querySelector("input");
    const listed = () => rendered.container.querySelectorAll('[role="option"]').length;

    act(() => input?.focus());
    expect(listed()).toBe(0);

    act(() => input?.click());
    expect(listed()).toBeGreaterThan(0);
  });

  it("shows no run counts before the runs are known", () => {
    const { input, options } = shown(null);
    act(() => input.focus());
    expect(options()[0]?.textContent).toBe(
      "Reference greenhousereference_greenhouse · organ-level tomato crop",
    );
  });

  it("narrows to the scenarios whose name, identifier or description holds what is typed", () => {
    const { input, options } = shown();
    act(() => input.focus());

    enter(input, "area");
    expect(options().map((option) => option.textContent?.slice(0, 12))).toEqual([
      "TOMGRO house",
      "Build a new ",
    ]);
    enter(input, "SENSOR_LAB");
    expect(options().map((option) => option.textContent?.slice(0, 10))).toEqual([
      "Sensor lab",
      "Build a ne",
    ]);
  });

  it("offers first, and opens on Enter, a scenario a search names, not one its description holds it in", () => {
    const { input, options, press, onChoose } = shown();
    act(() => input.focus());

    // "tom" is in the reference greenhouse's description, and in TOMGRO's name.
    enter(input, "tom");
    expect(options().map((option) => option.textContent?.slice(0, 12))).toEqual([
      "TOMGRO house",
      "Reference gr",
      "Build a new ",
    ]);
    press("Enter");
    expect(onChoose).toHaveBeenCalledExactlyOnceWith("tomgro_house");
  });

  it("says when nothing matches, and still offers to build one", () => {
    const { input, options } = shown();
    act(() => input.focus());
    enter(input, "nothing like it");

    expect(drawn?.container.textContent).toContain("No scenario matches “nothing like it”.");
    expect(options().map((option) => option.textContent)).toEqual(["Build a new scenario"]);
  });

  it("is chosen from by keyboard: the arrows move, Enter chooses, Escape closes", () => {
    const { input, options, press, onChoose, onBuild } = shown();
    act(() => input.focus());
    const active = () =>
      options().findIndex((option) => option.id === input.getAttribute("aria-activedescendant"));

    expect(active()).toBe(0);
    press("ArrowDown");
    press("ArrowDown");
    expect(active()).toBe(2);
    press("ArrowDown");
    press("ArrowDown");
    expect(active()).toBe(3);
    press("ArrowUp");
    expect(active()).toBe(2);
    press("Escape");
    expect(input.getAttribute("aria-expanded")).toBe("false");
    press("ArrowDown");
    expect(input.getAttribute("aria-expanded")).toBe("true");

    press("Enter");

    expect(onChoose).toHaveBeenCalledExactlyOnceWith("sensor_lab");
    expect(onBuild).not.toHaveBeenCalled();
    expect(input.getAttribute("aria-expanded")).toBe("false");
  });

  it("builds a scenario when the last entry is chosen, by keyboard or pointer", () => {
    const { input, options, press, pointOn, onChoose, onBuild } = shown();
    act(() => input.focus());
    for (let step = 0; step < SCENARIOS.length; step += 1) {
      press("ArrowDown");
    }
    press("Enter");
    expect(onBuild).toHaveBeenCalledTimes(1);

    // Focus stays in the box after a choice; a click opens the list again.
    act(() => input.click());
    pointOn(options().at(-1));
    expect(onBuild).toHaveBeenCalledTimes(2);
    expect(onChoose).not.toHaveBeenCalled();
  });

  it("is chosen from by pointer, and starts over empty for the next choice", () => {
    const { input, options, pointOn, onChoose } = shown();
    act(() => input.focus());
    enter(input, "tomgro");

    pointOn(options()[0]);

    expect(onChoose).toHaveBeenCalledExactlyOnceWith("tomgro_house");
    expect(input.value).toBe("");
    expect(input.getAttribute("aria-expanded")).toBe("false");
  });

  it("does nothing on Enter while closed", () => {
    const { input, press, onChoose } = shown();
    act(() => input.focus());
    press("Escape");
    press("Enter");
    expect(onChoose).not.toHaveBeenCalled();
  });

  it("opens a scenario whose identifier is the one the builder entry might have had", () => {
    const onChoose = vi.fn();
    const onBuild = vi.fn();
    const rendered = render(
      <ScenarioCombobox
        scenarios={[scenario("build", "Build", "a scenario that is named so")]}
        counts={null}
        onChoose={onChoose}
        onBuild={onBuild}
      />,
    );
    drawn = rendered;
    const input = rendered.container.querySelector("input") as HTMLInputElement;
    act(() => input.focus());
    const options = () => [...rendered.container.querySelectorAll('[role="option"]')];
    const pointOn = (option: Element | undefined) =>
      act(() => {
        option?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      });

    pointOn(options()[0]);
    expect(onChoose).toHaveBeenCalledExactlyOnceWith("build");
    expect(onBuild).not.toHaveBeenCalled();

    act(() => input.click());
    pointOn(options()[1]);
    expect(onBuild).toHaveBeenCalledTimes(1);
    expect(onChoose).toHaveBeenCalledTimes(1);
  });

  it("keeps the active option in view in the list when the arrows move it", () => {
    // Options 60 px tall in a list 180 px high: three show at a time.
    const spies: { mockRestore: () => void }[] = [
      vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(60),
      vi.spyOn(HTMLElement.prototype, "offsetTop", "get").mockImplementation(function (
        this: HTMLElement,
      ) {
        return Number(/-option-(\d+)$/.exec(this.id)?.[1] ?? 0) * 60;
      }),
      vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(180),
    ];
    const scrolled = new WeakMap<Element, number>();
    spies.push(
      vi.spyOn(Element.prototype, "scrollTop", "get").mockImplementation(function (this: Element) {
        return scrolled.get(this) ?? 0;
      }),
      vi.spyOn(Element.prototype, "scrollTop", "set").mockImplementation(function (
        this: Element,
        top: number,
      ) {
        scrolled.set(this, top);
      }),
    );
    try {
      const { input, press, options } = shown();
      act(() => input.focus());
      const list = document.getElementById(
        input.getAttribute("aria-controls") ?? "",
      ) as HTMLElement;

      press("ArrowDown");
      press("ArrowDown");
      expect(list.scrollTop).toBe(0);
      press("ArrowDown");
      // The fourth option, from 180 px to 240, is past the list's foot.
      expect(options()).toHaveLength(4);
      expect(list.scrollTop).toBe(60);
      press("ArrowUp");
      press("ArrowUp");
      expect(list.scrollTop).toBe(60);
      press("ArrowUp");
      expect(list.scrollTop).toBe(0);
    } finally {
      for (const spy of spies) {
        spy.mockRestore();
      }
    }
  });
});

describe("where an options list scrolls to", () => {
  const list = { scrollTop: 100, clientHeight: 180 };

  it("stays where it is while the option shows", () => {
    expect(scrolledTo(list, { offsetTop: 100, offsetHeight: 60 })).toBe(100);
    expect(scrolledTo(list, { offsetTop: 220, offsetHeight: 60 })).toBe(100);
  });

  it("goes the least that brings the option to the edge it is past", () => {
    expect(scrolledTo(list, { offsetTop: 40, offsetHeight: 60 })).toBe(40);
    expect(scrolledTo(list, { offsetTop: 240, offsetHeight: 60 })).toBe(120);
  });
});
