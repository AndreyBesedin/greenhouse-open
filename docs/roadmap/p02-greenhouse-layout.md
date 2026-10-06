# P02: Static greenhouse fixtures and layout

**Status:** in progress. Part of the [simulator roadmap](README.md).

## Goal

Populate the greenhouse with the fixed geometry that matters for cameras,
navigation, radiation and airflow: crop rows and planting positions, the
gutters, benches and slabs that carry them, walkways, rails, pipes and other
obstacles.

## Scope

Active climate equipment, such as fans and heaters, is left to the actuator
project (P05). The fixtures here are static geometric and semantic objects.

## Direction

- The layout is a description, like the envelope (decision
  [0016](../decisions/0016-the-greenhouse-has-its-own-frame.md)): given in the
  greenhouse's frame, and generating its fixtures. A scenario provides it
  today; a layout file or an editor can provide it later, and the geometry
  follows.
- Every fixture says what it is, what it is made of, and what it stands in
  the way of, so that robots, airflow and radiation can each collect their
  obstacles from the same description later.
- Planting positions are stable semantic entities: each has an identifier
  that does not change when an unrelated part of the layout does.
- Large repeated fixtures use instancing where it helps.

## Starting point

P01 gives the greenhouse its envelope: floor, walls, roof, gutters,
structural frames, doors and vents, all generated from an `Envelope`
description. Plants stand on a provisional grid built from the scenario's
rows and columns, at a fixed pitch and spacing in the scene module.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P02.1 | `feat(layout): define reusable fixture primitives` | Done ([#36](https://github.com/AndreyBesedin/greenhouse-open/pull/36)) |
| P02.2 | `feat(layout): generate crop rows and planting positions` | Done |
| P02.3 | `feat(layout): add gutters, tables, benches and slabs` | Planned |
| P02.4 | `feat(layout): add walkways, service zones and exclusion volumes` | Planned |
| P02.5 | `feat(layout): add rails, pipes and overhead structures` | Planned |
| P02.6 | `feat(layout): import and export the layout configuration` | Planned |
| P02.7 | `test(visual): add fixture occlusion and navigation QA scenes` | Planned |

### P02.1: Reusable fixture primitives

Box, cylinder, rail, pipe, tray and walkway primitives, with semantic tags,
flags for what they obstruct (movement, airflow), and configurable
materials. Visible result: a gallery of fixtures in the browser. Tests: each
primitive is drawn at exactly its configured dimensions.

As implemented (see [decision 0019](../decisions/0019-fixtures-say-what-they-are-made-of-and-what-they-obstruct.md)):

- A scenario's `layout` (`greenhouse_sim.world.layout.Layout`) describes what
  stands inside its greenhouse, in the greenhouse's frame. For now it holds
  fixtures placed one by one, each described by a primitive
  (`greenhouse_sim.world.fixtures`): a box, an upright cylinder, a pipe
  between two points, a rail of two tubes `gauge` apart, an open tray along a
  line (which may slope, and stays level across), and a walkway on the floor.
  The scenario refuses fixtures that share an identifier, or reach outside
  the greenhouse; a fixture reaching across a valley between spans must stay
  below the eaves there.
- Each fixture has a kind (crop gutter, walkway, rail, pipe or obstacle), the
  semantic tag; a material (steel, aluminium, plastic or concrete); and what
  it obstructs (movement, airflow, light), which radiation needs as much as
  airflow and robots do. Each kind brings defaults: a walkway obstructs
  nothing, a pipe or rail obstructs movement and light but not airflow.
- The scene shows each fixture as an entity of its kind, in its material's
  colour, with `obstructs_movement`, `obstructs_airflow` and
  `obstructs_light` as properties. Scene entities gain an optional
  `material`, so the scene schema moves to version 7. The viewer draws metal
  by material rather than by kind, and the envelope's frames (steel) and
  gutters (aluminium) state their materials; the inspector shows it.
- The fixture gallery, `?scene=fixtures` and a button beside the example
  scene, shows one fixture of each primitive in an 8 by 4.8 m greenhouse
  centred on the world's origin. The simulator writes it
  (`public/scenes/qa-fixtures.json`), and a test fails if the committed copy
  is stale.
- Tests:
  - Python: each primitive builds exactly its configured size and place: a
    box on its base, turned by its heading; a pipe from its start to its end
    along the length, across it, at a slant, straight up and straight down;
    a rail's tubes a gauge apart either side of its line; a sloping tray's
    bottom on its line, level across; a walkway on the floor. Rails whose
    tubes would touch, and lines without length, are refused. Kinds bring
    their defaults, and a description overrides them. The layout refuses
    shared identifiers, and fixtures through a wall, into the floor or up
    into a valley.
  - Viewer: the gallery's fixtures, as the viewer draws them, have their
    configured sizes and places. Boxes and cylinders are drawn by one
    geometry function (`solidGeometry`), shared by single meshes and
    instanced batches, so the test measures what is drawn.
  - Browser: each of the gallery's fixtures is picked from above, and the
    inspector shows its kind, size and material.

### P02.2: Crop rows and planting positions

Rows with an origin and a direction, row spacing, plant pitch, optional
paired rows, and a marker at each planting position. Visible result: the
greenhouse shows regular rows with visible plant positions. Tests: the
number of positions and their spacing can be measured from their debug
coordinates.

As implemented:

- A layout's `crop_rows` (`greenhouse_sim.world.rows.CropRows`) gives its
  rows: the first row's first planting position (`origin`), a `heading` (the
  rows run along the greenhouse's length at 0, and follow one another to the
  left of it), the number of rows and of positions per row, the
  `plant_pitch` along a row and the `row_spacing` across, and optionally a
  `pair_gap`, for rows in pairs. Every position is its own multiple of the
  pitch and spacing from the origin, so none drifts.
- Planting positions are named by their row and place along it,
  `row_<r>_position_<p>`, from 1. A scenario's plants stand at them in order,
  the first plant at the first row's first position, filling each row before
  the next; a scenario refuses a layout with fewer positions than plants, or
  positions outside its greenhouse. A refusal names the first three things
  outside and counts the rest.
- Every scenario now describes its rows. gh_demo and gh_002 keep the
  positions of the provisional grid they replace; gh_001's four rows of ten
  are now centred in its house, from (1.75, 2.4). The scene module's
  provisional pitch and spacing are gone.
- The scene marks each position with a disc on the floor, 12 cm across and
  wider than a stem, so that it shows around the plant on it, as a
  `PLANTING_POSITION` entity with its `row` and `position_in_row`; the scene
  schema moves to version 8. Each plant gains a `planting_position` property.
  The discs are cylinders, so they are drawn in one instanced batch.
- Tests:
  - Python: a position for every row and place, named in order; positions at
    the pitch along a row and the spacing across; a thousand positions along
    a row, each exactly its multiple of the pitch; rows turned a quarter run
    along +y and follow one another towards -x; paired rows a gap apart within
    a pair and a spacing from the next; pairs that would reach the next, too
    few positions for the plants, and positions outside the greenhouse are
    refused. The scene marks each position where it stands, placed with the
    greenhouse, and stands each plant on its position, in order.
  - Browser: in gh_001, three plants and a marker are picked; the inspector
    gives their coordinates (0.5 m along a row, 1.6 m to the next) and
    their positions' names, and colouring by `row` and `position_in_row`
    counts four rows of ten.

### P02.3: Gutters, tables, benches and slabs

Generic support structures, with their height, width, length and offsets,
and presets for a tomato gutter and for a bench or table. Visible result:
the rows are physically supported, not floating markers.

### P02.4: Walkways, service zones and exclusion volumes

A central aisle, side aisles, service zones and keep-out volumes, coloured
distinctly in a debug view. Visible result: a top view clearly shows the
operational layout. Tests: no planting position is generated inside an
exclusion volume.

### P02.5: Rails, pipes and overhead structures

A robot rail, heating pipes as passive geometry for now, overhead crop
wires, and configurable repeated pipe runs. Visible result: a more credible
interior, with structures overhead and at floor level.

### P02.6: Layout configuration files

A declarative layout file per scenario, with stable identifiers, and an
inspector that shows each fixture's semantic type and dimensions. Visible
result: switching between two different layouts without changing any code.

### P02.7: Fixture occlusion and navigation QA scenes

A camera between the rows, a close-up with fixtures occluding the view, and
a top-down view of the layout, as screenshot baselines.

## Final QA: `greenhouse-layout`

Inspect two scenarios' layouts, measure the row and plant spacing, check that
walkways stay clear, inspect rails and pipes from inside the rows, check
semantic selection, and check the visual snapshots.

## Acceptance criteria

- [ ] The layout is entirely data-driven.
- [ ] Fixed objects can later be exported as airflow, radiation or robot
  obstacles.
- [ ] Planting positions are stable semantic entities.
- [ ] Large repeated fixtures use instancing where appropriate.
