import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { OpeningControls, openingsIn } from "./OpeningControls";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { searchFor, sourceFromSearch } from "./scene/source";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/example.json", import.meta.url), "utf8"),
);
const ignore = () => undefined;

describe("a scene's openings", () => {
  it("are its doors and vents, with how far each stands open", () => {
    // The climate box's: one of each kind, all shut.
    expect(openingsIn(EXAMPLE)).toEqual([
      { openingId: "roof_vent", label: "roof vent", fraction: 0, apertureM2: 0 },
      { openingId: "side_vent", label: "side vent", fraction: 0, apertureM2: 0 },
      { openingId: "side_vent_left", label: "side vent left", fraction: 0, apertureM2: 0 },
      { openingId: "door", label: "door", fraction: 0, apertureM2: 0 },
    ]);
  });

  it("each get a slider showing the fraction asked for, and what the scene says", () => {
    const html = renderToStaticMarkup(
      <OpeningControls snapshot={EXAMPLE} requested={{ roof_vent: 0.6 }} onChange={ignore} />,
    );

    expect(html).toContain('aria-label="Openings"');
    // The slider shows what was asked; the reading, what the scene says.
    expect(html).toContain('value="60"');
    expect(html).toContain('data-testid="opening-roof_vent">0%, 0 m²<');
    expect(html).toContain('data-testid="opening-door">0%, 0 m²<');
  });

  it("are kept in the address bar, for the simulator's API to apply", () => {
    const source = sourceFromSearch("?scenario=climate_box&open=roof_vent_1:0.5,door_1:1");

    expect(source).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
      openings: { roof_vent_1: 0.5, door_1: 1 },
    });
    expect(searchFor(source)).toBe("?scenario=climate_box&open=door_1:1,roof_vent_1:0.5");
    expect(sourceFromSearch("?scenario=climate_box&open=roof_vent_1:wide")).toEqual({
      kind: "scenario",
      scenarioId: "climate_box",
    });
  });
});
