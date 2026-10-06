# P02: Static greenhouse fixtures and layout

**Status:** done. Part of the [simulator roadmap](README.md).

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
| P02.2 | `feat(layout): generate crop rows and planting positions` | Done ([#38](https://github.com/AndreyBesedin/greenhouse-open/pull/38)) |
| P02.3 | `feat(layout): add gutters, tables, benches and slabs` | Done ([#39](https://github.com/AndreyBesedin/greenhouse-open/pull/39)) |
| P02.4 | `feat(layout): add walkways, service zones and exclusion volumes` | Done ([#40](https://github.com/AndreyBesedin/greenhouse-open/pull/40)) |
| P02.5 | `feat(layout): add rails, pipes and overhead structures` | Done ([#41](https://github.com/AndreyBesedin/greenhouse-open/pull/41)) |
| P02.6 | `feat(layout): import and export the layout configuration` | Done ([#42](https://github.com/AndreyBesedin/greenhouse-open/pull/42)) |
| P02.7 | `test(visual): add fixture occlusion and navigation QA scenes` | Done ([#43](https://github.com/AndreyBesedin/greenhouse-open/pull/43)) |

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

As implemented:

- Crop rows may have a `support` (`greenhouse_sim.world.rows.RowSupport`): a
  generic structure along each row, of a kind (crop gutter or bench), with
  the height of its top, its width and depth, how far it reaches beyond the
  row's first and last positions (`overhang`), how far it lies beside the row
  (`offset`), its material, legs at most `leg_spacing` apart (or none, when it
  hangs from the structure), and optionally a substrate `slab` along its top.
  The planting positions stand on the slab, or on the top.
- Each row's support is generated from its row: the top (`row_<r>_support_1`)
  laid along the row, the legs (`..._leg_<k>`) evenly spaced from end to end
  under it, from the floor to its underside, and the slab (`row_<r>_slab_1`),
  stopping 5 cm short of each end. The `_1` leaves room for a row split into
  several supports, around a walkway (P02.4).
- Presets: `TOMATO_GUTTER`, a galvanised steel gutter 30 cm wide and 12 cm
  deep, its top at 60 cm, on stands at most 2 m apart, with a stone wool slab
  20 cm wide and 7.5 cm high; and `BENCH`, an aluminium top 1.2 m wide at
  80 cm, on legs at most 1.5 m apart, for plants in pots. The plan's "tomato
  gutter and rail preset" is split: the pipe rail between rows comes with
  P02.5's rails.
- gh_001's four rows grow in tomato gutters. gh_demo's and gh_002's crops
  stay in the soil, on the floor: they are the small walkthrough houses, and
  their scenes stay as they were.
- New fixture kinds `BENCH` and `SLAB`, and a `substrate` material, so the
  scene schema moves to version 9. Legs take their support's kind, so the
  categories' colours show them as part of it, and, being cylinders, they are
  drawn in instanced batches.
- Tests:
  - Python: planting positions stand on the slab; each row's support reaches
    the overhang beyond its first and last positions, at its height, width
    and depth; legs stand evenly from end to end, never further apart than
    their spacing, from the floor to the underside; a hung support has none;
    the slab lies on the top, short of its ends; a support can lie beside its
    row and follows the rows' heading; the bench preset carries pots at
    80 cm without a slab; a support too deep for its height, or reaching
    through a wall, is refused; the scene draws each part as its kind.
  - Browser: in gh_001, a gutter, its first leg and its slab are picked, with
    their kinds, sizes and materials; the plants' coordinates now read the
    slab's height.

### P02.4: Walkways, service zones and exclusion volumes

A central aisle, side aisles, service zones and keep-out volumes, coloured
distinctly in a debug view. Visible result: a top view clearly shows the
operational layout. Tests: no planting position is generated inside an
exclusion volume.

As implemented:

- Walkways are the walkway fixtures placed in a layout. A layout's `zones`
  (`greenhouse_sim.world.zones`) are service zones (room for carts, trolleys,
  irrigation and climate units) and keep-out volumes (where robots and
  trolleys must not go), each a strip of the floor (a centre line and a
  width) rising to a height.
- No planting position lies inside a walkway, service zone or keep-out
  volume; the others keep their identifiers, so a row crossed by an aisle
  numbers on across it. On a support, a position is also left out unless its
  support can reach 10 cm beyond it, so that every plant stands on its slab.
- A row's support runs under each unbroken run of its positions, numbered
  along the row (`row_<r>_support_<k>`, `row_<r>_slab_<k>`), and stops short
  of any area kept clear that any part of its width would reach into. The
  end legs stand flush with a support's ends.
- Walkways stay clear: a layout that puts anything obstructing movement on
  one is refused. Fixtures and zones share no identifier, and zones must fit
  inside the greenhouse.
- gh_001 gains an aisle across its front, past its door, and one along its
  right side wall, a service zone across its back, and an irrigation unit
  there with a keep-out volume around it. All forty of its positions stay.
- The scene shows zones as the volumes they keep (`SERVICE_ZONE`,
  `KEEP_OUT`), see-through like glazing; the scene schema moves to version
  10. A click ranks what it hits: anything solid first, then a zone's
  volume, then the floor, then glazing, so a click on the floor inside a
  zone picks the zone.
- The categories' debug view ("Categories", formerly "Surface categories")
  now also colours the layout, from Paul Tol's muted palette, with a second
  legend, "Layout categories".
- `/qa/layout?view=top` shows the canonical layout from above, coloured by
  category, cut just below the eaves so that the roof does not hide it. The
  canonical layout (`public/scenes/qa-layout.json`, written by the simulator)
  is the QA greenhouse with five rows of tomato gutters split by a central
  aisle, aisles across the front and along the right side wall, a service
  zone at the back, and a keep-out volume around an electrical cabinet that
  cuts the last row short. P02.7 adds its other views and baselines.
- Tests:
  - Python: a strip holds what lies inside it but not on its edge; where a
    band along a line reaches into it, square, along it, past its end and
    beside it. No position lies in a walkway, service zone or keep-out
    volume, and the others keep their names. A row crossed by an aisle gets
    a support on each side, stopping at it, with its last plant still on its
    slab; a support stops short of a keep-out volume. A cabinet on a walkway,
    or a pipe across one, is refused; something obstructing only light may
    cross. Over a grid of 60 aisles and keep-out volumes, no position lies
    inside any area, every support, leg and slab keeps clear of them, and
    every position stands on a slab. Zones are drawn as the volumes they
    keep, turned with their strips.
  - Viewer: zones are picked over the floor, but not over what stands in
    them; the layout's categories have colours of their own, cover the
    canonical layout, and have a legend of their own; the QA top view looks
    down on the house's middle, cut below its eaves.
  - Browser: in gh_001, the layout's legend lists its categories, the front
    aisle is picked as a walkway that obstructs nothing, and the service
    zone is picked from the front. The QA layout's top view draws without
    console errors.

### P02.5: Rails, pipes and overhead structures

A robot rail, heating pipes as passive geometry for now, overhead crop
wires, and configurable repeated pipe runs. Visible result: a more credible
interior, with structures overhead and at floor level.

As implemented:

- Crop rows may have `rails` (`RowRails`): a pipe rail along the middle of
  each path between neighbouring rows wide enough for it, beside their
  supports. `PIPE_RAIL` is 51 mm heating pipes 55 cm apart, their axes 10 cm
  up: in tomato greenhouses the rails trolleys and robots ride on are the
  heating pipes, so with P02.3's gutter this makes the plan's tomato gutter
  and rail preset. Rails stop short of the areas kept clear, as supports do,
  in pieces (`rail_<g>_<k>`, for the path after row `g`); a piece shorter than
  a metre is not laid.
- Crop rows may have `wires` (`CropWires`): a crop wire above each run of a
  row's positions, as long as its support, which the plants are trained up
  to. A new `WIRE` kind obstructs nothing; the scene schema moves to version
  11.
- A new primitive, a pipe run (`PipeRunPrimitive`), repeats a pipe a step
  apart, each its own multiple of the step: heating pipes stacked along a
  wall, or pipes repeated across the house.
- Walkways stay clear only up to a doorway's height, 2.1 m: above it, pipes
  may cross them.
- gh_001 gains a pipe rail between each pair of its rows, a crop wire 3 m up
  above each, and four heating pipes stacked along each side wall. The
  canonical QA layout gains the same, its rails and wires in pieces either
  side of its central aisle.
- Every rail tube, pipe and wire is a cylinder, so all of them are drawn in
  instanced batches. Wires are drawn at their real 5 mm, which is barely
  visible from a distance, as from a camera.
- Tests:
  - Python: a rail along the middle of each path between rows, at its
    height and gauge; none where paired rows leave too narrow a path; in
    pieces either side of an aisle, stopping at its edges; none for a piece
    too short to ride on. A crop wire above each run, as long as its gutter,
    or reaching beyond its row without one. A pipe run repeats its pipe a step
    apart, and refuses pipes that would touch. A pipe may cross a walkway
    above head height, not below it.
  - Browser: in gh_001, from above, a rail tube and the top heating pipe are
    picked, with their kinds, sizes and what they obstruct.

### P02.6: Layout configuration files

A declarative layout file per scenario, with stable identifiers, and an
inspector that shows each fixture's semantic type and dimensions. Visible
result: switching between two different layouts without changing any code.

As implemented (see [decision 0020](../decisions/0020-scenario-layouts-are-declarative-json-files.md)):

- Each scenario's layouts are JSON files,
  `greenhouse_sim/scenarios/layouts/<scenario>/<name>.json`, each a `Layout`
  as the model writes it, naming the published JSON Schema it follows
  (`scenarios/layout.schema.json`, kept current by a test). `default.json`
  is the layout a scenario is defined with; the three scenarios now read
  theirs from files, and draw exactly the scenes they drew before. gh_001
  has a second layout, `benches.json`: the same rows, aisles, zones and
  pipes, with the plants on benches instead of gutters.
- The layout's descriptions refuse fields they do not have, so a typo in a
  file is an error. A layout's name can only be lower case letters, digits
  and underscores, so it cannot reach outside its scenario's folder.
- The local API lists each scenario's layouts, shows a scenario with another
  of them (`?layout=benches`), and writes a scenario's layout as its file
  holds it (`GET /api/scenarios/{id}/layout`). A changed envelope is now
  checked with the scenario's layout too: before, a smaller greenhouse could
  leave its layout outside it unnoticed.
- The viewer's scenarios table offers a picker for a scenario with several
  layouts; the address keeps the choice. The inspector now says what the
  selected entity is in words ("crop gutter"), and names its dimensions: a
  box's length, width and height, a cylinder's diameter and its height
  standing or length lying.
- Tests:
  - Python: the published schema matches the model; each scenario's layout
    is its default file; every layout file fits its scenario; every file is
    exactly what its layout writes, and reads back to the same fixtures and
    positions, identifiers and all; a name cannot reach another folder; a
    misspelt field is refused; the bench layout keeps the same positions on
    benches. The API shows the bench layout, writes it as its file holds
    it, and refuses an unknown layout, a name reaching another folder, and a
    greenhouse shrunk below its layout, with the reason.
  - Viewer: the scenario list reads layouts, refuses summaries without
    them, and offers a picker only where there is a choice; the address
    round-trips `layout=`; the inspector names a gutter's type and
    dimensions, and a plant's height and a pipe's length.
  - Browser: gh_001's layout is switched to benches in the picker, a bench
    is picked with its type and dimensions, a reload keeps the layout, and
    switching back restores the default.

### P02.7: Fixture occlusion and navigation QA scenes

A camera between the rows, a close-up with fixtures occluding the view, and
a top-down view of the layout, as screenshot baselines.

As implemented:

- `/qa/layout?view=top|between-rows|occluded` shows the canonical layout
  (P02.4) from three fixed views: the plan from above, coloured by category
  and cut below the eaves; a camera on a trolley riding the rail down the
  second path, a metre up, looking down it to the back of the house; and a
  camera low in the first path, between its rail's tubes, looking across the
  second row, which its gutter, legs and the rail tubes partly hide. Only
  the plan is coloured and cut.
- CI's visual checks job compares the three views with their baselines,
  drawn in its pinned container, as P00.7's and P01.7's are.
- Tests: the views are chosen in the address; the trolley camera stands
  between the rail's tubes, under the wires, looking along the path; the low
  camera stands below the gutters' tops, looking past the next row; only the
  plan is cut and coloured. A browser test draws all three views without
  console errors, with the legends on the plan only.

## Final QA: `greenhouse-layout`

Inspect two scenarios' layouts, measure the row and plant spacing, check that
walkways stay clear, inspect rails and pipes from inside the rows, check
semantic selection, and check the visual snapshots.

As implemented ([#44](https://github.com/AndreyBesedin/greenhouse-open/pull/44)):

- `tests/test_greenhouse_layout.py` checks the layout's promises over a grid
  of 128 layouts: two greenhouses (24 by 9.6 m and 48 by 19.2 m), rows along
  the length and across it, pitches of 0.4 and 0.5 m, rows 1.6 or 2 m apart
  or in pairs, on the floor, on gutters or on benches, with and without
  aisles across them and a keep-out volume over them, and with rails, wires
  and heating pipes. In each: the layout fits its greenhouse; every position
  lies its multiple of the pitch along its row and its row's offset across;
  no position lies in an area kept clear; every supported plant stands on
  its slab or bench; walkways stay clear below head height; identifiers are
  unique and survive a layout file; and every fixture is an obstacle to what
  it obstructs, and to nothing else. Benches too wide for paired rows are
  refused: a new check refuses rows too close for their supports. The grid
  takes about 20 seconds, so it is marked slow: the full checks and CI run
  it, the quick pre-push pass does not.
- `Layout.obstructing(obstruction)` gives the fixtures that stand in the way
  of movement, airflow or light: the obstacles robots, airflow and radiation
  will take from the layout.
- `e2e/greenhouse-layout.spec.ts` walks through it in the browser: gh_001's
  default layout, coloured by category, its cylinders in a few instanced
  batches; a gutter and a walkway selected as what they are, the walkway
  obstructing nothing; three plants' coordinates giving the pitch and row
  spacing; a rail and a heating pipe picked from above; the bench layout
  switched to, with the same spacing at bench height; its layout written out
  by the API as data; and the canonical layout seen from between its rows.
- The viewer's cylinder batching is a function of its own
  (`cylinderBatches`), which a test holds to one batch per kind and finish:
  the canonical layout's hundreds of cylinders are six draw calls. Grouping
  them no longer copies each batch as it grows.
- The screenshots are compared by CI's visual checks job (P02.7).

## Acceptance criteria

- [x] The layout is entirely data-driven: every scenario reads its layout
  from a JSON file, checked against the model and a published schema, and a
  second layout is a second file (decision
  [0020](../decisions/0020-scenario-layouts-are-declarative-json-files.md)).
- [x] Fixed objects can later be exported as airflow, radiation or robot
  obstacles: each fixture says what it obstructs (decision
  [0019](../decisions/0019-fixtures-say-what-they-are-made-of-and-what-they-obstruct.md)),
  and `Layout.obstructing` collects the obstacles for each.
- [x] Planting positions are stable semantic entities: each is named by its
  row and place along it, keeps its name when an aisle or zone takes its
  neighbours, and survives a layout file; plants name the position they
  stand at.
- [x] Large repeated fixtures use instancing where appropriate: planting
  positions, legs, rail tubes, pipes, wires and frames are cylinders, drawn
  in one instanced batch per kind and finish. On the development machine
  (Apple M2, Chromium on the graphics card, the frame rate not tied to the
  display), a 100 by 48 m greenhouse of ten spans and 25 bays, with 28 rows
  of tomato gutters split by a central aisle, 5,320 planting positions,
  1,400 legs, 108 rail tubes and 56 wires (7,846 entities), runs at about
  460 frames per second while orbiting, 2.2 ms per frame, in 206 draw calls.
  Gutters and slabs are boxes, one draw call each; at that cost they are not
  yet worth batching.

## Later

- An editor in the viewer that changes a layout through the local API, in
  the shape of a layout file (decision 0020).
- Batching boxes as cylinders are batched, if gutters and slabs by the
  hundred ever cost frames.
