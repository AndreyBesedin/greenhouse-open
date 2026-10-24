// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import {
  button,
  checkbox,
  choose,
  click,
  enter,
  type Rendered,
  render,
  select,
} from "../testing/render";
import type { Installation } from "./generated/assessedTypes";
import type { Edit } from "./generated/editTypes";
import { fieldValue, Items } from "./Items";

const HOUSE = {
  installation_id: "house",
  name: "House",
  envelope: {
    openings: [
      {
        opening_id: "vent_1",
        kind: "roof_vent",
        surface_id: "roof_1_right",
        centre: { x: -4, y: 0 },
        width: 1,
        height: 0.6,
      },
    ],
  },
  layout: {
    equipment: [
      {
        actuator_id: "heater_1",
        kind: "heater",
        base: { x: 1, y: 0.6, z: 0 },
        size_x: 0.6,
        size_y: 0.8,
        size_z: 1.2,
        power_w: 10_000,
      },
      {
        actuator_id: "heater_2",
        kind: "heater",
        base: { x: 3, y: 0.6, z: 0 },
        size_x: 0.6,
        size_y: 0.8,
        size_z: 1.2,
        power_w: 10_000,
      },
    ],
    sensors: [
      { sensor_id: "temperature_1", kind: "temperature", position: { x: 6, y: 3, z: 1.5 } },
    ],
  },
  row_crops: [],
} as unknown as Installation;

// The roof slopes and a wall of the house, as the simulator draws them.
const SCENE = {
  greenhouse_id: "house",
  entities: [
    { entity_id: "house_floor", kind: "FLOOR", shape: { shape: "plane", size_x: 12, size_y: 6 } },
    {
      entity_id: "house_roof_1_right",
      kind: "ROOF",
      shape: { shape: "plane", size_x: 12, size_y: 1.58 },
    },
    {
      entity_id: "house_roof_1_left",
      kind: "ROOF",
      shape: { shape: "plane", size_x: 12, size_y: 1.58 },
    },
    {
      entity_id: "house_side_wall_right",
      kind: "WALL",
      shape: { shape: "plane", size_x: 12, size_y: 4 },
    },
  ],
} as unknown as SceneSnapshot;

/** The number field labelled `name`, by the label around it. */
function field(within: ParentNode, name: string): HTMLInputElement {
  const found = [...within.querySelectorAll<HTMLInputElement>("input")].filter(
    (input) => input.closest("label")?.firstChild?.textContent?.trim() === name,
  );
  if (found.length !== 1 || found[0] === undefined) {
    throw new Error(`no one field labelled "${name}"`);
  }
  return found[0];
}

function chosen(within: ParentNode, id: string): HTMLInputElement {
  const found = within.querySelector<HTMLInputElement>(`input[aria-label="Choose ${id}"]`);
  if (found === null) {
    throw new Error(`no box to choose ${id}`);
  }
  return found;
}

describe("the builder's equipment, sensors, doors and vents (P12.3)", () => {
  let shown: Rendered | undefined;
  afterEach(() => shown?.unmount());

  /** The section, its choice kept as the builder keeps it. */
  function Choosing({ onEdit }: { onEdit: (edit: Edit, said: string) => void }) {
    const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
    return (
      <Items
        installation={HOUSE}
        snapshot={SCENE}
        chosen={chosen}
        busy={false}
        onChoose={setChosen}
        onEdit={onEdit}
      />
    );
  }

  function show(onEdit = vi.fn()) {
    shown = render(<Choosing onEdit={onEdit} />);
    return { within: shown.container, onEdit };
  }

  it("lists each item, its kind and where it is", () => {
    const { within } = show();

    const rows = [...within.querySelectorAll("tbody tr")].map((row) => row.textContent);
    expect(rows).toEqual([
      "heater_1heater1 m, 0.6 m, 0 m",
      "heater_2heater3 m, 0.6 m, 0 m",
      "temperature_1temperature6 m, 3 m, 1.5 m",
      "vent_1roof ventroof 1 right, -4 m along",
    ]);
  });

  it("places several pieces of equipment at a step, in one edit", () => {
    const { within, onEdit } = show();

    choose(select(within, "What"), "heater");
    enter(field(within, "How many"), "3");
    enter(field(within, "Step along x (m)"), "2");
    click(button(within, "Place"));

    const [edit, said] = onEdit.mock.calls[0] ?? [];
    expect(edit).toMatchObject({
      edit: "place_items",
      item: { actuator_id: "heater", kind: "heater", base: { x: 1, y: 1, z: 0 } },
      count: 3,
      step: { x: 2, y: 0, z: 0 },
    });
    expect(said).toBe("Placed 3 heaters.");
  });

  it("spreads roof vents along each slope chosen, offering only the roof", () => {
    const { within, onEdit } = show();

    choose(select(within, "What"), "roof_vent");
    expect(button(within, "Place").disabled).toBe(true);
    expect(() => checkbox(within, "side wall right")).toThrow();
    click(checkbox(within, "roof 1 right"));
    click(checkbox(within, "roof 1 left"));
    click(button(within, "Place"));

    expect(onEdit.mock.calls[0]?.[0]).toMatchObject({
      edit: "spread_openings",
      opening: { kind: "roof_vent", width: 1, height: 0.6, centre: { y: 0 } },
      surfaces: ["roof_1_right", "roof_1_left"],
      count: 4,
    });
  });

  it("places a door at the foot of the wall chosen", () => {
    const { within, onEdit } = show();

    choose(select(within, "What"), "door");
    click(checkbox(within, "side wall right"));
    click(checkbox(within, "Spread evenly along each"));
    enter(field(within, "How many on each"), "1");
    click(button(within, "Place"));

    expect(onEdit.mock.calls[0]?.[0]).toMatchObject({
      edit: "place_openings",
      opening: { kind: "door", surface_id: "side_wall_right", centre: { x: 0, y: -2 + 2.1 / 2 } },
      surfaces: ["side_wall_right"],
      count: 1,
    });
  });

  it("copies, spaces, changes and removes the items chosen", () => {
    const { within, onEdit } = show();

    click(chosen(within, "heater_1"));
    click(chosen(within, "heater_2"));
    enter(field(within, "Copies of each"), "2");
    click(button(within, "Copy"));
    enter(field(within, "Field"), "power_w");
    enter(field(within, "Value"), "20000");
    click(button(within, "Set it on each"));
    click(button(within, "Remove"));

    expect(onEdit.mock.calls.map(([edit]) => edit)).toEqual([
      {
        edit: "repeat_items",
        items: ["heater_1", "heater_2"],
        count: 2,
        step: { x: 1, y: 0, z: 0 },
      },
      { edit: "set_field", items: ["heater_1", "heater_2"], path: "power_w", value: 20000 },
      { edit: "remove_items", items: ["heater_1", "heater_2"] },
    ]);
    // Spacing takes three at least.
    expect(button(within, "Space evenly").disabled).toBe(true);
  });

  it("copies or spaces items of one kind only: in the house or on a surface", () => {
    const { within } = show();

    click(chosen(within, "heater_1"));
    click(chosen(within, "vent_1"));

    expect(() => button(within, "Copy")).toThrow();
    expect(within.textContent).toContain("Choose equipment and sensors, or doors and vents");
    expect(button(within, "Remove").disabled).toBe(false);
  });

  it("reads a field's value as a number or a flag where it is one", () => {
    expect([fieldValue("2.5"), fieldValue("true"), fieldValue("fan_2"), fieldValue(" ")]).toEqual([
      2.5,
      true,
      "fan_2",
      " ",
    ]);
  });
});
