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
    expect(openingsIn(EXAMPLE)).toEqual([
      {
        openingId: "roof_vent_1",
        label: "roof vent 1",
        fraction: 0.25,
        apertureM2: expect.any(Number),
      },
      {
        openingId: "roof_vent_2",
        label: "roof vent 2",
        fraction: 0.25,
        apertureM2: expect.any(Number),
      },
      { openingId: "side_vent_1", label: "side vent 1", fraction: 0, apertureM2: 0 },
      { openingId: "door_1", label: "door 1", fraction: 0, apertureM2: 0 },
    ]);
  });

  it("each get a slider showing the fraction asked for, and what the scene says", () => {
    const html = renderToStaticMarkup(
      <OpeningControls snapshot={EXAMPLE} requested={{ roof_vent_1: 0.6 }} onChange={ignore} />,
    );

    expect(html).toContain('aria-label="Openings"');
    expect(html).toContain('value="60"');
    expect(html).toContain('data-testid="opening-roof_vent_1">25%, 0.26 m²<');
    expect(html).toContain('data-testid="opening-door_1">0%, 0 m²<');
  });

  it("are kept in the address bar, for the simulator's API to apply", () => {
    const source = sourceFromSearch("?scenario=gh_demo&open=roof_vent_1:0.5,door_1:1");

    expect(source).toEqual({
      kind: "scenario",
      scenarioId: "gh_demo",
      openings: { roof_vent_1: 0.5, door_1: 1 },
    });
    expect(searchFor(source)).toBe("?scenario=gh_demo&open=door_1:1,roof_vent_1:0.5");
    expect(sourceFromSearch("?scenario=gh_demo&open=roof_vent_1:wide")).toEqual({
      kind: "scenario",
      scenarioId: "gh_demo",
    });
  });
});
