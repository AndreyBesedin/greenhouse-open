import { useState } from "react";

import { type OverlayToggles, type SceneOverlay, SELECTION_COLOR } from "./debug/overlays";
import type { FieldView } from "./fields/display";
import { FLOW_COLOR } from "./fields/openingFlows";
import { PROBE_COLOR } from "./fields/probes";
import type { SceneEntityKind } from "./scene/generated/snapshotTypes";
import { FRUSTUM_COLOR } from "./sensors/camera";
import { SUN_COLOR, WIND_COLOR } from "./weather/weather";

// The colours of what the scene draws itself, as the simulator and the
// view draw them (scene/snapshot.py, Viewport.tsx), and of a scale, a
// category's and the CFD boundaries' colours as the card hints at them.
const GRID_COLOR = "#888888";
const AXES_COLORS = "linear-gradient(90deg, #e03c31 33%, #2e9e44 33% 66%, #2f6fd6 66%)";
const PLANTING_COLOR = "#d99940";
const GLASS_COLOR = "#9ec7e0";
const EQUIPMENT_OFF_COLOR = "#8c8c8c";
const SCALE_COLORS = "linear-gradient(90deg, #440154, #21918c, #fde725)";
const CATEGORY_COLORS = "linear-gradient(90deg, #e69f00, #56b4e9, #009e73)";
const CFD_COLOR = "#999999";
const EQUIPMENT_KINDS: readonly SceneEntityKind[] = ["FAN", "HEATER", "DEHUMIDIFIER"];
const GLAZED_KINDS: readonly SceneEntityKind[] = ["WALL", "ROOF", "VENT"];

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
  colourBy: string | null;
  byCategory: boolean;
  cfdBoundaries: boolean;
  dimensions: boolean;
  /** The kinds the scene holds; null while the empty grid is shown. */
  kinds: ReadonlySet<SceneEntityKind> | null;
}

const OVERLAYS: Record<Exclude<SceneOverlay, "airField">, Omit<SeenRow, "key">> = {
  openingFlows: {
    glyph: "arrow",
    color: FLOW_COLOR,
    name: "Flows through openings",
    meaning: "Air in or out of each open door or vent: a metre of arrow per m³/s.",
  },
  wind: {
    glyph: "arrow",
    color: WIND_COLOR,
    name: "Wind",
    meaning: "The wind outside, the way it blows: a metre of arrow per m/s.",
  },
  sun: {
    glyph: "dot",
    color: SUN_COLOR,
    name: "Sun and its path",
    meaning: "Where the sun is now, and its path through the day, its height and bearing in °.",
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

/** The air field as it is drawn, and what its colours measure. */
function airField(view: FieldView, scale: { title: string; unit: string } | null): SeenRow {
  const measured = scale === null ? "" : ` Its colours: ${scale.title} (${scale.unit}).`;
  const meaning = {
    arrows: "The air's velocity in each cell: an arrow's length and colour, its speed.",
    streamlines: "The air's paths, traced through the field from seeds across it.",
    slice: "A plane through the air, each cell coloured by what it measures.",
  }[view];
  return {
    key: "airField",
    glyph: view === "slice" ? "square" : "arrow",
    color: SCALE_COLORS,
    name: `Air field ${view}`,
    meaning: `${meaning}${measured}`,
  };
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
  const overlays = shown.map((overlay) =>
    overlay === "airField"
      ? airField(view.fieldView, view.fieldScale)
      : { key: overlay, ...OVERLAYS[overlay] },
  );
  const hidden = view.drawn
    .filter((overlay) => !view.overlays[overlay])
    .map((overlay) =>
      overlay === "airField" ? `air field ${view.fieldView}` : OVERLAYS[overlay].name.toLowerCase(),
    );

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
      color: CATEGORY_COLORS,
      name: "Categories",
      meaning: "Each entity coloured by what it is: the legend below.",
    });
  }
  if (view.cfdBoundaries) {
    colours.push({
      key: "cfd",
      glyph: "square",
      color: CFD_COLOR,
      name: "CFD boundaries",
      meaning: "The faces the air's mesh is bounded by, by kind: the legend below.",
    });
  }
  if (view.dimensions) {
    colours.push({
      key: "dimensions",
      glyph: "line",
      color: SELECTION_COLOR,
      name: "Dimensions and axis labels",
      meaning: "Each entity's size, and the selected one's axes.",
    });
  }

  return { overlays, colours, always: always(view.kinds), hidden };
}

/** What the scene always draws: the ground grid, the world's axes, and,
 * where the scene holds them, its glass, planting positions and equipment. */
function always(kinds: ReadonlySet<SceneEntityKind> | null): SeenRow[] {
  const rows: SeenRow[] = [
    {
      key: "grid",
      glyph: "line",
      color: GRID_COLOR,
      name: "Ground grid",
      meaning: "20 m across, in 1 m cells.",
    },
  ];
  if (kinds === null || kinds.has("AXES")) {
    rows.push({
      key: "axes",
      glyph: "line",
      color: AXES_COLORS,
      name: "World axes",
      meaning: "2 m long from the origin: x red, y green, z blue.",
    });
  }
  if (kinds === null) {
    return rows;
  }
  if (GLAZED_KINDS.some((kind) => kinds.has(kind))) {
    rows.push({
      key: "glass",
      glyph: "square",
      color: GLASS_COLOR,
      name: "Glass",
      meaning: "Walls, roof and vents, drawn see-through.",
    });
  }
  if (kinds.has("PLANTING_POSITION")) {
    rows.push({
      key: "planting",
      glyph: "dot",
      color: PLANTING_COLOR,
      name: "Planting positions",
      meaning: "A disc on the floor where a plant can stand.",
    });
  }
  if (EQUIPMENT_KINDS.some((kind) => kinds.has(kind))) {
    rows.push({
      key: "equipment",
      glyph: "square",
      color: EQUIPMENT_OFF_COLOR,
      name: "Equipment",
      meaning: "Grey while off, in its kind's colour while running. A fan's arrow shows its way.",
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
