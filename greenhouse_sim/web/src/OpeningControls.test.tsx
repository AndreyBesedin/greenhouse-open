import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { describeOpenings, OpeningControls, openingsIn } from "./OpeningControls";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { searchFor, sourceFromSearch } from "./scene/source";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../public/scenes/example.json", import.meta.url), "utf8"),
);
const ignore = () => undefined;
const OPEN = { open: true, onToggle: ignore };

describe("a scene's openings", () => {
  it("are its doors and vents, with how far each stands open", () => {
    // The climate box's: one of each kind, all shut.
    expect(openingsIn(EXAMPLE)).toEqual([
      { openingId: "roof_vent", label: "roof vent", kind: "roof_vent", fraction: 0, apertureM2: 0 },
      { openingId: "side_vent", label: "side vent", kind: "side_vent", fraction: 0, apertureM2: 0 },
      {
        openingId: "side_vent_left",
        label: "side vent left",
        kind: "side_vent",
        fraction: 0,
        apertureM2: 0,
      },
      { openingId: "door", label: "door", kind: "door", fraction: 0, apertureM2: 0 },
    ]);
  });

  it("each get a slider showing the fraction asked for, and what the scene says", () => {
    const html = renderToStaticMarkup(
      <OpeningControls
        snapshot={EXAMPLE}
        requested={{ roof_vent: 0.6 }}
        fold={OPEN}
        onChange={ignore}
      />,
    );

    expect(html).toContain('aria-label="Openings"');
    // The slider shows what was asked; the reading, what the scene says.
    expect(html).toContain('value="60"');
    expect(html).toContain('data-testid="opening-roof_vent">0%, 0 m²<');
    expect(html).toContain('data-testid="opening-door">0%, 0 m²<');
  });

  it("are folded to a line that says how far each stands open", () => {
    const vent = {
      openingId: "roof_vent_1",
      label: "roof vent 1",
      kind: "roof_vent",
      fraction: 1,
      apertureM2: 2.9,
    };
    const door = { openingId: "door", label: "door", kind: "door", fraction: 0, apertureM2: 0 };
    const html = renderToStaticMarkup(
      <OpeningControls snapshot={EXAMPLE} requested={{}} fold={OPEN} onChange={ignore} />,
    );

    expect(html).toContain('<details class="ds-fold openings-fold" open="">');
    expect(html).toContain('data-testid="openings-summary">Openings: all shut</span></summary>');
    // By kind (P22.8), a kind whose pieces stand apart by piece.
    const second = { ...vent, openingId: "roof_vent_2", label: "roof vent 2" };
    expect(describeOpenings([vent, second, door])).toBe("Openings: roof vents 100%; door shut");
    expect(describeOpenings([vent, { ...second, fraction: 0.5 }, door])).toBe(
      "Openings: roof vent 1 100%, roof vent 2 50%; door shut",
    );
  });

  it("are listed by kind, under the kind's name, each by what tells it apart", () => {
    const html = renderToStaticMarkup(
      <OpeningControls snapshot={EXAMPLE} requested={{}} fold={OPEN} onChange={ignore} />,
    );

    expect(html).toContain('<p class="opening-group">Side vents</p>');
    // Its words name the vent within its kind; its slider keeps the vent's name.
    expect(html).toContain('<span>left</span><input type="range" aria-label="side vent left"');
    // A kind of one is listed by its own name, with no heading.
    expect(html).toContain('<span>door</span><input type="range" aria-label="door"');
    expect(html).not.toContain('class="opening-group">Door');
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
