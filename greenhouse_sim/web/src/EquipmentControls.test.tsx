import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { describeLevel, EquipmentControls, equipmentIn } from "./EquipmentControls";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { changesQuery, searchFor, sourceFromSearch } from "./scene/source";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/example.json", import.meta.url), "utf8"),
);
const ignore = () => undefined;

describe("a scene's equipment", () => {
  it("is its fans, heaters and dehumidifiers, each at its level, with what it does at full", () => {
    // The climate box's: one of each, all off.
    expect(equipmentIn(EXAMPLE)).toEqual([
      { actuatorId: "fan", label: "fan", level: 0, rated: 1, unit: "m³/s" },
      { actuatorId: "heater", label: "heater", level: 0, rated: 10, unit: "kW" },
      { actuatorId: "dehumidifier", label: "dehumidifier", level: 0, rated: 5, unit: "kg/h" },
    ]);
  });

  it("says what each does at its level", () => {
    const heater = { actuatorId: "heater", label: "heater", level: 0, rated: 10, unit: "kW" };

    expect(describeLevel(heater)).toBe("off");
    expect(describeLevel({ ...heater, level: 0.5 })).toBe("50%, 5 kW");
    expect(describeLevel({ ...heater, level: 0.35 })).toBe("35%, 3.50 kW");
  });

  it("each get a switch and a slider showing the level asked for, and what the scene says", () => {
    const html = renderToStaticMarkup(
      <EquipmentControls snapshot={EXAMPLE} requested={{ heater: 0.6 }} onChange={ignore} />,
    );

    expect(html).toContain('aria-label="Equipment"');
    // The controls show what was asked; the reading, what the scene says.
    expect(html).toContain('aria-label="heater level" min="0" max="100" step="5" value="60"');
    expect(html.match(/type="checkbox" checked=""/g)).toHaveLength(1);
    expect(html).toContain('data-testid="equipment-heater">off<');
    expect(html).toContain('data-testid="equipment-fan">off<');
  });

  it("leaves a scene without equipment without the panel", () => {
    const bare = { ...EXAMPLE, entities: EXAMPLE.entities.filter((e) => e.kind === "FLOOR") };

    expect(
      renderToStaticMarkup(<EquipmentControls snapshot={bare} requested={{}} onChange={ignore} />),
    ).toBe("");
  });

  it("is kept in the address bar, for the simulator's API to apply", () => {
    const source = sourceFromSearch("?scenario=climate_box&open=door:1&set=heater:0.5,fan:1");

    expect(source).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      openings: { door: 1 },
      levels: { heater: 0.5, fan: 1 },
    });
    expect(searchFor(source)).toBe("?scenario=climate_box&open=door:1&set=fan:1,heater:0.5");
    expect(changesQuery({ levels: { fan: 1 } }, "?")).toBe("?set=fan:1");
    expect(sourceFromSearch("?scenario=climate_box&set=fan:full")).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
    });
  });
});
