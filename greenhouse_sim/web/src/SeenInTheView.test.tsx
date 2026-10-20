// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { CFD_COLORS } from "./cfd/boundaries";
import { CATEGORY_COLORS } from "./debug/categories";
import { DIMENSION_COLOR } from "./debug/dimensions";
import { ALL_OVERLAYS } from "./debug/overlays";
import { CUBE_COLOR, PLACEHOLDER_AXES_LENGTH_M } from "./emptyView";
import { qaScene } from "./qa/qaScene";
import {
  type SeenRow,
  seenInTheView,
  type ViewState,
  WhatAmISeeing,
  worldAxesLength,
} from "./SeenInTheView";
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
  fieldArrowSpacing: 1,
  sun: { now: true, path: true },
  colourBy: null,
  byCategory: false,
  cfdBoundaries: false,
  dimensions: false,
  kinds: HOUSE,
  axesLengthM: 1,
};
// The view before a scene: the grid, the empty view's axes and its cube.
const EMPTY: ViewState = {
  ...VIEW,
  drawn: [],
  kinds: null,
  axesLengthM: PLACEHOLDER_AXES_LENGTH_M,
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
    // The empty view: the grid, its axes and its cube, and nothing of a house.
    expect(names(seenInTheView(EMPTY).always)).toEqual(["Ground grid", "World axes", "A 1 m cube"]);
    expect(
      names(seenInTheView({ ...VIEW, kinds: new Set(["FLOOR"]), axesLengthM: null }).always),
    ).toEqual(["Ground grid"]);
  });
});

// Each row says what the view draws, as it draws it (the Codex review of #241).
describe("each row matches what is drawn", () => {
  const row = (rows: readonly SeenRow[], key: string) =>
    rows.find((candidate) => candidate.key === key);

  it("explains the cube the empty view draws for scale, and its 2 m axes", () => {
    const { always } = seenInTheView(EMPTY);

    expect(row(always, "cube")).toEqual({
      key: "cube",
      glyph: "square",
      color: CUBE_COLOR,
      name: "A 1 m cube",
      meaning: "For scale, on the grid cell from (1, 1) to (2, 2) m, until a scene is shown.",
    });
    expect(row(always, "axes")).toMatchObject({
      meaning: "2 m long from the origin: x red, y green, z blue.",
    });
    expect(row(seenInTheView(VIEW).always, "cube")).toBeUndefined();
  });

  it("gives a scene's axes their own length, and the empty view's its own", () => {
    expect(row(seenInTheView(VIEW).always, "axes")).toMatchObject({
      meaning: "1 m long from the origin: x red, y green, z blue.",
    });
    expect(worldAxesLength(null)).toBe(PLACEHOLDER_AXES_LENGTH_M);
    expect(worldAxesLength(qaScene(1))).toBe(1);
    const noAxes = qaScene(1);
    expect(
      worldAxesLength({
        ...noAxes,
        entities: noAxes.entities.filter((entity) => entity.kind !== "AXES"),
      }),
    ).toBeNull();
  });

  it("gives the scene's rows their categories' colours while categories are shown", () => {
    const { always } = seenInTheView({ ...VIEW, byCategory: true });

    expect(row(always, "glass")).toMatchObject({
      color: `linear-gradient(90deg, ${CATEGORY_COLORS.WALL}, ${CATEGORY_COLORS.ROOF})`,
      meaning:
        "Walls, roof and vents, drawn see-through. Each in its category's colour: the legend below.",
    });
    expect(row(always, "planting")).toMatchObject({ color: CATEGORY_COLORS.PLANTING_POSITION });
    expect(row(always, "equipment")).toMatchObject({
      color: CATEGORY_COLORS.FAN,
      meaning:
        "Running or not. A fan's arrow shows its way. Each in its category's colour: the legend below.",
    });
  });

  it("says a colouring shades the scene's rows where they have its value", () => {
    const { always } = seenInTheView({ ...VIEW, colourBy: "age_days" });

    expect(row(always, "equipment")?.meaning).toBe(
      "Grey while off, in its kind's colour while running. A fan's arrow shows its way. " +
        "Shaded by age_days where it has a value.",
    );
    expect(row(always, "grid")?.meaning).toBe("20 m across, in 1 m cells.");
  });

  it("draws the dimensions in their own blue, and says what they measure", () => {
    const { colours } = seenInTheView({ ...VIEW, dimensions: true });

    expect(row(colours, "dimensions")).toMatchObject({
      color: DIMENSION_COLOR,
      meaning:
        "The greenhouse's length, width and height along its floor edges, and the axes' names.",
    });
  });

  it("gives the CFD boundaries their kinds' colours", () => {
    const cfd = row(seenInTheView({ ...VIEW, cfdBoundaries: true }).colours, "cfd");

    expect(cfd?.color).toBe(`linear-gradient(90deg, ${Object.values(CFD_COLORS).join(", ")})`);
  });

  it("says an opening's arrow is held between its shortest and longest", () => {
    const flows = seenInTheView({ ...VIEW, drawn: ["openingFlows"] }).overlays[0];

    expect(flows?.meaning).toBe(
      "Air in or out of each open door or vent: 1 m of arrow per m³/s, " +
        "never shorter than 0.5 m nor longer than 3 m.",
    );
  });

  it("names only the halves of the sun that are drawn, shown or hidden", () => {
    const sun = (now: boolean, path: boolean) =>
      seenInTheView({ ...VIEW, drawn: ["sun"], sun: { now, path } }).overlays[0];

    expect(sun(true, false)).toMatchObject({
      name: "Sun",
      meaning: "Where the sun is now, its height and bearing in °.",
    });
    expect(sun(false, true)).toMatchObject({
      name: "Sun's path",
      meaning: "The sun's path through the day.",
    });
    expect(sun(true, true)?.name).toBe("Sun and its path");
    const hidden = seenInTheView({
      ...VIEW,
      drawn: ["sun"],
      sun: { now: false, path: true },
      overlays: { ...ALL_OVERLAYS, sun: false },
    });
    expect(hidden.hidden).toEqual(["sun's path"]);
  });

  it("says when a big field's arrows stand only every few cells", () => {
    expect(seenInTheView(VIEW).overlays[0]?.meaning).toContain("The air's velocity in each cell:");
    const thinned = seenInTheView({ ...VIEW, fieldArrowSpacing: 2 }).overlays[0];

    expect(thinned?.meaning).toBe(
      "The air's velocity in one cell in 2 along x and y, a big field thinned to draw quickly: " +
        "an arrow's length and colour, its speed. Its colours: air speed (m/s).",
    );
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
