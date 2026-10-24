// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { choose, type Rendered, render } from "../testing/render";
import type { Installation } from "./generated/assessedTypes";
import { Inspector } from "./Inspector";

const HOUSE = {
  installation_id: "house",
  name: "House",
  envelope: {
    length: 12,
    width: 6,
    eave_height: 4,
    ridge_height: 4.5,
    spans: 2,
    bays: 3,
    openings: [
      {
        opening_id: "vent_1",
        kind: "roof_vent",
        surface_id: "roof_1_right",
        centre: { x: -4, y: 0 },
        width: 1,
        height: 0.6,
        opening: 0,
        largest_angle: 0.5,
      },
    ],
  },
  layout: {
    crop_rows: {
      rows: 2,
      pair_gap: 0.4,
      support: { kind: "crop_gutter", height: 0.5, width: 0.3, depth: 0.12 },
    },
    equipment: [
      {
        actuator_id: "heater_1",
        kind: "heater",
        heading: 0,
        base: { x: 1, y: 0.6, z: 0 },
        size_x: 0.6,
        size_y: 0.8,
        size_z: 1.2,
        power_w: 10_000,
      },
    ],
    zones: [
      {
        zone_id: "service_1",
        kind: "service",
        area: { start: { x: 11, y: 0.5 }, end: { x: 11, y: 1.5 }, width: 0.8 },
        height: 2,
      },
    ],
    placed: [
      {
        primitive: "pipe_run",
        fixture_id: "heating_1",
        start: { x: 0.5, y: 1, z: 0.1 },
        end: { x: 11.5, y: 1, z: 0.1 },
        radius: 0.03,
        count: 2,
        step: { x: 0, y: 0.2, z: 0 },
      },
    ],
  },
  row_crops: [],
} as unknown as Installation;

/** The input or select labelled `name`, by the label around it. */
function control(within: ParentNode, name: string): HTMLInputElement | HTMLSelectElement {
  const found = [
    ...within.querySelectorAll<HTMLInputElement | HTMLSelectElement>("input, select"),
  ].filter((each) => each.closest("label")?.firstChild?.textContent?.trim() === name);
  if (found.length !== 1 || found[0] === undefined) {
    throw new Error(`no one control labelled "${name}"`);
  }
  return found[0];
}

/** `text` typed into `input`, then Enter, which leaves it. */
function typeAndEnter(input: HTMLInputElement | HTMLSelectElement, text: string): void {
  act(() => {
    input.focus();
    input.value = text;
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  });
}

describe("the builder's inspector (P12.3)", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  function show(chosen: string | null, onEdit = vi.fn()) {
    shown = render(<Inspector installation={HOUSE} chosen={chosen} busy={false} onEdit={onEdit} />);
    return { within: shown.container, onEdit };
  }

  it("shows every field of the item chosen, and sets one by its path", () => {
    const { within, onEdit } = show("heater_1");

    expect(within.querySelector("h2")?.textContent).toBe("heater_1");
    expect(control(within, "Base Y").value).toBe("0.6");
    typeAndEnter(control(within, "Power W"), "20000");
    typeAndEnter(control(within, "Base Z"), "0.5");

    expect(onEdit.mock.calls).toEqual([
      [
        { edit: "set_field", items: ["heater_1"], path: "power_w", value: 20000 },
        "Set power w of heater_1.",
      ],
      [
        { edit: "set_field", items: ["heater_1"], path: "base.z", value: 0.5 },
        "Set base z of heater_1.",
      ],
    ]);
  });

  it("sends nothing for a field left as it was", () => {
    const { within, onEdit } = show("heater_1");

    typeAndEnter(control(within, "Power W"), "10000");

    expect(onEdit).not.toHaveBeenCalled();
  });

  it("offers a door or vent's kind as a choice", () => {
    const { within, onEdit } = show("vent_1");

    const kind = control(within, "Kind");
    expect(kind.value).toBe("roof_vent");
    choose(kind as HTMLSelectElement, "side_vent");

    expect(onEdit.mock.calls[0]?.[0]).toEqual({
      edit: "set_field",
      items: ["vent_1"],
      path: "kind",
      value: "side_vent",
    });
  });

  it("shows the fields of a model the rows may hold, and sets an emptied field that may be none to null", () => {
    const { within, onEdit } = show(null);

    expect(control(within, "Support Height").value).toBe("0.5");
    typeAndEnter(control(within, "Pair Gap"), "");
    typeAndEnter(control(within, "Support Height"), "0.6");

    expect(onEdit.mock.calls.map(([edit]) => edit)).toEqual([
      { edit: "set_value", path: "layout.crop_rows.pair_gap", value: null },
      { edit: "set_value", path: "layout.crop_rows.support.height", value: 0.6 },
    ]);
  });

  it("shows a zone's or a fixture's fields, the ends of an area among them", () => {
    const { within, onEdit } = show("service_1");

    expect(control(within, "Area End Y").value).toBe("1.5");
    typeAndEnter(control(within, "Area Start X"), "10");
    shown?.unmount();
    const pipes = show("heating_1");
    typeAndEnter(control(pipes.within, "Count"), "3");

    expect([...onEdit.mock.calls, ...pipes.onEdit.mock.calls].map(([edit]) => edit)).toEqual([
      { edit: "set_field", items: ["service_1"], path: "area.start.x", value: 10 },
      { edit: "set_field", items: ["heating_1"], path: "count", value: 3 },
    ]);
  });

  it("shows the house's fields when no one item is chosen, each set by its path", () => {
    const { within, onEdit } = show(null);

    expect(within.querySelector("h2")?.textContent).toBe("Envelope and rows");
    expect(control(within, "Length").value).toBe("12");
    typeAndEnter(control(within, "Length"), "14");
    typeAndEnter(control(within, "Rows"), "3");

    expect(onEdit.mock.calls.map(([edit]) => edit)).toEqual([
      { edit: "set_value", path: "envelope.length", value: 14 },
      { edit: "set_value", path: "layout.crop_rows.rows", value: 3 },
    ]);
  });
});
