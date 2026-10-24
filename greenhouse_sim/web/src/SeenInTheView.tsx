import { useState } from "react";

import { CFD_COLORS } from "./cfd/boundaries";
import {
  CATEGORY_COLORS,
  type Category,
  EQUIPMENT_CATEGORIES,
  type EquipmentCategory,
} from "./debug/categories";
import { DIMENSION_COLOR } from "./debug/dimensions";
import type { OverlayToggles, SceneOverlay } from "./debug/overlays";
import {
  CUBE_COLOR,
  CUBE_CORNER_M,
  CUBE_SIZE_M,
  GRID_COLORS,
  GRID_DIVISIONS,
  GRID_SIZE_M,
  PLACEHOLDER_AXES_LENGTH_M,
} from "./emptyView";
import type { FieldView } from "./fields/display";
import {
  ARROW_M_PER_M3_S,
  FLOW_COLOR,
  LONGEST_ARROW_M,
  SHORTEST_ARROW_M,
} from "./fields/openingFlows";
import { PROBE_COLOR } from "./fields/probes";
import type { SceneEntityKind, SceneSnapshot } from "./scene/generated/snapshotTypes";
import { FRUSTUM_COLOR } from "./sensors/camera";
import { SUN_COLOR, WIND_COLOR } from "./weather/weather";

// The colours of what the scene draws itself, as the simulator draws them
// (scene/snapshot.py), and of a scale as the card hints at it.
const AXES_COLORS = "linear-gradient(90deg, #e03c31 33%, #2e9e44 33% 66%, #2f6fd6 66%)";
const PLANTING_COLOR = "#d99940";
const GLASS_COLOR = "#9ec7e0";
const EQUIPMENT_OFF_COLOR = "#8c8c8c";
const SCALE_COLORS = "linear-gradient(90deg, #440154, #21918c, #fde725)";
// The categories' swatch: the first three of their colours, as a hint.
const CATEGORY_HINT: readonly Category[] = ["FLOOR", "WALL", "ROOF"];
const GLAZED_KINDS = ["WALL", "ROOF", "VENT"] as const satisfies readonly Category[];

/** One thing in the view, and what it means. */
export interface SeenRow {
  key: string;
  /** How its swatch is drawn: an arrow, a dot, a line or a square. */
  glyph: "arrow" | "dot" | "line" | "square";
  /** Its colour in the view: a CSS colour, or a gradient for several. */
  color: string;
  name: string;
  meaning: string;
}

/** What the view draws, as the card lists it. */
export interface Seen {
  /** The overlays over the scene that are shown. */
  overlays: SeenRow[];
  /** How the scene's own colours and labels are chosen. */
  colours: SeenRow[];
  /** What the scene always draws. */
  always: SeenRow[];
  /** The overlays a switch has hidden, by name. */
  hidden: string[];
}

/** What the view is drawing, read from the same state the view is drawn
 * from: so that the card never explains something that isn't drawn. */
export interface ViewState {
  /** The overlays over the scene that have something to draw. */
  drawn: readonly SceneOverlay[];
  overlays: OverlayToggles;
  fieldView: FieldView;
  /** What the air field's colours measure, if one is drawn. */
  fieldScale: { title: string; unit: string } | null;
  /** How many cells apart the air field's arrows stand along x and y: 1
   * on every cell, more on a field too big for that (`arrowSpacing`). */
  fieldArrowSpacing: number;
  /** Which of the sun overlay's two halves have something to draw: the sun
   * where it is now (above the horizon only), and its path through the day,
   * each loaded on its own. */
  sun: { now: boolean; path: boolean };
  colourBy: string | null;
  byCategory: boolean;
  cfdBoundaries: boolean;
  dimensions: boolean;
  /** The kinds the scene holds, and its equipment's categories; null while
   * the empty view is shown. */
  kinds: ReadonlySet<SceneEntityKind | EquipmentCategory> | null;
  /** How long the world axes are drawn, in metres: the scene's own, or the
   * empty view's; null when none are drawn. */
  axesLengthM: number | null;
}

/** How long the world axes are drawn, in metres: a scene's own axes marker,
 * one metre in the simulator's scenes, or the empty view's two; null for a
 * scene that holds none. */
export function worldAxesLength(snapshot: SceneSnapshot | null): number | null {
  if (snapshot === null) {
    return PLACEHOLDER_AXES_LENGTH_M;
  }
  const axes = snapshot.entities.find((entity) => entity.kind === "AXES");
  return axes?.shape.shape === "axes" ? axes.shape.length : null;
}

type OverlayRow = Omit<SeenRow, "key">;

const OVERLAYS: Record<Exclude<SceneOverlay, "airField" | "sun">, OverlayRow> = {
  openingFlows: {
    glyph: "arrow",
    color: FLOW_COLOR,
    name: "Flows through openings",
    meaning:
      `Air in or out of each open door or vent: ${ARROW_M_PER_M3_S} m of arrow per m³/s, ` +
      `never shorter than ${SHORTEST_ARROW_M} m nor longer than ${LONGEST_ARROW_M} m.`,
  },
  wind: {
    glyph: "arrow",
    color: WIND_COLOR,
    name: "Wind",
    meaning: "The wind outside, the way it blows: a metre of arrow per m/s.",
  },
  cameraViews: {
    glyph: "line",
    color: FRUSTUM_COLOR,
    name: "Camera views",
    meaning: "What each camera sees, outlined from its eye.",
  },
  probes: {
    glyph: "dot",
    color: PROBE_COLOR,
    name: "Probes",
    meaning: "Where the drawn field is read, each named, with the air's arrow there.",
  },
};

/** The sun overlay as far as it draws: the sun now, its day's path, or both. */
function sunRow({ now, path }: ViewState["sun"]): OverlayRow {
  const looks = { glyph: "dot", color: SUN_COLOR } as const;
  if (now && !path) {
    return { ...looks, name: "Sun", meaning: "Where the sun is now, its height and bearing in °." };
  }
  if (path && !now) {
    return { ...looks, name: "Sun's path", meaning: "The sun's path through the day." };
  }
  return {
    ...looks,
    name: "Sun and its path",
    meaning: "Where the sun is now, its height and bearing in °, and its path through the day.",
  };
}

/** The air field as it is drawn, and what its colours measure. */
function airField(view: ViewState): SeenRow {
  const { fieldView, fieldScale, fieldArrowSpacing } = view;
  const measured =
    fieldScale === null ? "" : ` Its colours: ${fieldScale.title} (${fieldScale.unit}).`;
  const where =
    fieldArrowSpacing > 1
      ? `in one cell in ${fieldArrowSpacing} along x and y, a big field thinned to draw quickly`
      : "in each cell";
  const meaning = {
    arrows: `The air's velocity ${where}: an arrow's length and colour, its speed.`,
    streamlines: "The air's paths, traced through the field from seeds across it.",
    slice: "A plane through the air, each cell coloured by what it measures.",
  }[fieldView];
  return {
    key: "airField",
    glyph: fieldView === "slice" ? "square" : "arrow",
    color: SCALE_COLORS,
    name: `Air field ${fieldView}`,
    meaning: `${meaning}${measured}`,
  };
}

function overlayRow(overlay: SceneOverlay, view: ViewState): SeenRow {
  if (overlay === "airField") {
    return airField(view);
  }
  return { key: overlay, ...(overlay === "sun" ? sunRow(view.sun) : OVERLAYS[overlay]) };
}

/** A swatch for one colour or several. */
function swatch(colors: readonly string[]): string {
  return colors.length === 1 ? (colors[0] ?? "") : `linear-gradient(90deg, ${colors.join(", ")})`;
}

/**
 * What the view draws, row by row (#205): the overlays over the scene that
 * are shown, how the scene's colours are chosen, and what the scene always
 * draws, each with its colour, its name and what it means; and the
 * overlays hidden. It only reads the view's state: it asks for nothing and
 * changes nothing drawn.
 */
export function seenInTheView(view: ViewState): Seen {
  const shown = view.drawn.filter((overlay) => view.overlays[overlay]);
  const overlays = shown.map((overlay) => overlayRow(overlay, view));
  const hidden = view.drawn
    .filter((overlay) => !view.overlays[overlay])
    .map((overlay) => overlayRow(overlay, view).name.toLowerCase());

  const colours: SeenRow[] = [];
  if (view.colourBy !== null) {
    colours.push({
      key: "colourBy",
      glyph: "square",
      color: SCALE_COLORS,
      name: `Coloured by ${view.colourBy}`,
      meaning: "Each entity shaded by its value, over the scene's range: the legend below.",
    });
  }
  if (view.byCategory) {
    colours.push({
      key: "categories",
      glyph: "square",
      color: swatch(CATEGORY_HINT.map((category) => CATEGORY_COLORS[category])),
      name: "Categories",
      meaning: "Each entity coloured by what it is: the legend below.",
    });
  }
  if (view.cfdBoundaries) {
    colours.push({
      key: "cfd",
      glyph: "square",
      color: swatch(Object.values(CFD_COLORS)),
      name: "CFD boundaries",
      meaning:
        "The faces the air's mesh is bounded by, each in its kind's colour: the legend below.",
    });
  }
  if (view.dimensions) {
    colours.push({
      key: "dimensions",
      glyph: "line",
      color: DIMENSION_COLOR,
      name: "Dimensions and axis labels",
      meaning:
        "The greenhouse's length, width and height along its floor edges, and the axes' names.",
    });
  }

  return { overlays, colours, always: always(view), hidden };
}

/** What the scene always draws: the ground grid, the world's axes, and,
 * where the scene holds them, its glass, planting positions and equipment,
 * in their own colours unless a colour mode puts its own on them
 * (`SceneView`'s `shownColor`); or, before a scene, a cube for scale. */
function always(view: ViewState): SeenRow[] {
  const { kinds, axesLengthM, byCategory, colourBy } = view;
  const rows: SeenRow[] = [
    {
      key: "grid",
      glyph: "line",
      color: GRID_COLORS.centre,
      name: "Ground grid",
      meaning: `${GRID_SIZE_M} m across, in ${GRID_SIZE_M / GRID_DIVISIONS} m cells.`,
    },
  ];
  if (axesLengthM !== null) {
    rows.push({
      key: "axes",
      glyph: "line",
      color: AXES_COLORS,
      name: "World axes",
      meaning: `${axesLengthM} m long from the origin: x red, y green, z blue.`,
    });
  }
  if (kinds === null) {
    const far = CUBE_CORNER_M + CUBE_SIZE_M;
    rows.push({
      key: "cube",
      glyph: "square",
      color: CUBE_COLOR,
      name: `A ${CUBE_SIZE_M} m cube`,
      meaning:
        `For scale, on the grid cell from (${CUBE_CORNER_M}, ${CUBE_CORNER_M}) ` +
        `to (${far}, ${far}) m, until a scene is shown.`,
    });
    return rows;
  }
  // A colour mode's colours replace an entity's own: the category's for
  // every one of these, or the colouring's where it has the value.
  const own = (color: string, meaning: string, held: readonly Category[]) =>
    byCategory
      ? {
          color: swatch(held.map((kind) => CATEGORY_COLORS[kind])),
          meaning: `${meaning} Each in its category's colour: the legend below.`,
        }
      : {
          color,
          meaning:
            colourBy === null ? meaning : `${meaning} Shaded by ${colourBy} where it has a value.`,
        };
  const glazed = GLAZED_KINDS.filter((kind) => kinds.has(kind));
  if (glazed.length > 0) {
    rows.push({
      key: "glass",
      glyph: "square",
      name: "Glass",
      ...own(GLASS_COLOR, "Walls, roof and vents, drawn see-through.", glazed),
    });
  }
  if (kinds.has("PLANTING_POSITION")) {
    rows.push({
      key: "planting",
      glyph: "dot",
      name: "Planting positions",
      ...own(PLANTING_COLOR, "A disc on the floor where a plant can stand.", ["PLANTING_POSITION"]),
    });
  }
  const equipment = EQUIPMENT_CATEGORIES.filter((category) => kinds.has(category));
  if (equipment.length > 0) {
    rows.push({
      key: "equipment",
      glyph: "square",
      name: "Equipment",
      ...own(
        EQUIPMENT_OFF_COLOR,
        byCategory
          ? "Running or not. A fan's arrow shows its way."
          : "Grey while off, in the colour of what it is for while running. A fan's arrow shows its way.",
        equipment,
      ),
    });
  }
  return rows;
}

/**
 * "What am I seeing?" (#205): a button at the top of the legends, which
 * opens a card listing what the view draws (`seenInTheView`), above the
 * legends that measure it. Closed at first; × closes it, and the button
 * stays to open it again.
 */
export function WhatAmISeeing({ view }: { view: ViewState }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button type="button" className="seen-open" onClick={() => setOpen(true)}>
        What am I seeing?
      </button>
    );
  }
  const seen = seenInTheView(view);
  return (
    <section className="seen-in-the-view" aria-label="What am I seeing?">
      <header>
        <h2>What am I seeing?</h2>
        <button type="button" aria-label="Close what am I seeing" onClick={() => setOpen(false)}>
          ×
        </button>
      </header>
      <Rows rows={seen.overlays} />
      <Rows rows={seen.colours} />
      <Rows rows={seen.always} />
      {seen.hidden.length > 0 && <p data-testid="seen-hidden">Hidden: {seen.hidden.join(", ")}.</p>}
    </section>
  );
}

function Rows({ rows }: { rows: readonly SeenRow[] }) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <dl>
      {rows.map((row) => (
        <div key={row.key} data-testid={`seen-${row.key}`}>
          <dt>
            <span
              className={`seen-glyph seen-${row.glyph}`}
              aria-hidden="true"
              style={{ background: row.color }}
            />
            {row.name}
          </dt>
          <dd>{row.meaning}</dd>
        </div>
      ))}
    </dl>
  );
}
