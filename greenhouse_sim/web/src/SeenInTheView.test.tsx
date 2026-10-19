// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { ALL_OVERLAYS } from "./debug/overlays";
import { seenInTheView, type ViewState, WhatAmISeeing } from "./SeenInTheView";
import type { SceneEntityKind } from "./scene/generated/snapshotTypes";
import { button, click, type Rendered, render, said } from "./testing/render";

const HOUSE: ReadonlySet<SceneEntityKind> = new Set([
  "AXES",
  "FLOOR",
  "WALL",
  "ROOF",
  "PLANTING_POSITION",
  "FAN",
]);
const VIEW: ViewState = {
  drawn: ["airField", "wind", "sun", "probes"],
  overlays: ALL_OVERLAYS,
  fieldView: "arrows",
  fieldScale: { title: "air speed", unit: "m/s" },
  colourBy: null,
  byCategory: false,
  cfdBoundaries: false,
  dimensions: false,
  kinds: HOUSE,
};
const names = (rows: readonly { name: string }[]) => rows.map(({ name }) => name);

describe("what the view is drawing, explained", () => {
  it("lists each overlay shown, the air field as it is drawn and what its colours measure", () => {
    const seen = seenInTheView(VIEW);

    expect(names(seen.overlays)).toEqual([
      "Air field arrows",
      "Wind",
      "Sun and its path",
      "Probes",
    ]);
    expect(seen.overlays[0]?.meaning).toContain("Its colours: air speed (m/s).");
    expect(seen.overlays[1]?.meaning).toBe(
      "The wind outside, the way it blows: a metre of arrow per m/s.",
    );
    expect(seen.hidden).toEqual([]);
    const slice = seenInTheView({
      ...VIEW,
      fieldView: "slice",
      fieldScale: { title: "temperature", unit: "°C" },
    });
    expect(slice.overlays[0]?.name).toBe("Air field slice");
    expect(slice.overlays[0]?.meaning).toContain("temperature (°C)");
  });

  it("leaves out an overlay hidden by its switch, and says it is hidden", () => {
    const seen = seenInTheView({
      ...VIEW,
      overlays: { ...ALL_OVERLAYS, wind: false, airField: false },
    });

    expect(names(seen.overlays)).toEqual(["Sun and its path", "Probes"]);
    expect(seen.hidden).toEqual(["air field arrows", "wind"]);
  });

  it("explains the colour modes in effect, and only those", () => {
    expect(seenInTheView(VIEW).colours).toEqual([]);
    const coloured = seenInTheView({
      ...VIEW,
      colourBy: "age_days",
      byCategory: true,
      cfdBoundaries: true,
      dimensions: true,
    });

    expect(names(coloured.colours)).toEqual([
      "Coloured by age_days",
      "Categories",
      "CFD boundaries",
      "Dimensions and axis labels",
    ]);
  });

  it("says what the scene always draws, as far as the scene holds it", () => {
    expect(names(seenInTheView(VIEW).always)).toEqual([
      "Ground grid",
      "World axes",
      "Glass",
      "Planting positions",
      "Equipment",
    ]);
    // The empty grid: the grid and the axes, and nothing of a house.
    expect(names(seenInTheView({ ...VIEW, drawn: [], kinds: null }).always)).toEqual([
      "Ground grid",
      "World axes",
    ]);
    expect(names(seenInTheView({ ...VIEW, kinds: new Set(["FLOOR"]) }).always)).toEqual([
      "Ground grid",
    ]);
  });
});

describe("the What am I seeing? card", () => {
  let card: Rendered | undefined;
  afterEach(() => card?.unmount());

  it("is closed at first, opens by its button, and closes with ×, its button back", () => {
    card = render(<WhatAmISeeing view={VIEW} />);
    expect(card.container.querySelector("section")).toBeNull();

    click(button(card.container, "What am I seeing?"));
    expect(card.container.querySelector("h2")?.textContent).toBe("What am I seeing?");
    expect(said(card.container, "seen-wind")).toContain("Wind");

    click(button(card.container, "Close what am I seeing"));
    expect(card.container.querySelector("section")).toBeNull();
    expect(button(card.container, "What am I seeing?")).toBeDefined();
  });

  it("follows the view: an overlay hidden leaves the card at once", () => {
    card = render(<WhatAmISeeing view={VIEW} />);
    click(button(card.container, "What am I seeing?"));

    card.rerender(<WhatAmISeeing view={{ ...VIEW, overlays: { ...ALL_OVERLAYS, wind: false } }} />);

    expect(said(card.container, "seen-wind")).toBeNull();
    expect(said(card.container, "seen-hidden")).toBe("Hidden: wind.");
  });
});
