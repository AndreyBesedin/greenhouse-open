# P01: Greenhouse envelope and world geometry

**Status:** in progress. Part of the [simulator roadmap](README.md).

## Goal

Turn the empty viewer into a dimensionally correct greenhouse: a stable
coordinate system and a configurable envelope, with floor, walls, roof,
structure and openings.

## Direction

- SI units, and the world axes of
  [decision 0007](../decisions/0007-world-coordinates-metres-right-handed-z-up.md).
  The greenhouse has its own origin and axes within the world, and both are
  explicit.
- Geometry is generated from a semantic description of the greenhouse (its
  dimensions, spans, bays and openings), never modelled as meshes. Scenarios
  provide that description today; an editor in the viewer could change it
  later, and the geometry would follow.
- Rendering and, later, physics and airflow derive their geometry from the
  same semantic description of the greenhouse.
- Every envelope surface carries a semantic tag: floor, glazing, wall, roof,
  door or vent opening. Openings are described so that they can later become
  airflow boundaries (P04).

## Starting point

Decision 0007 fixes the world's axes and units. P00 provides the viewer this
project draws in: a typed renderer per entity kind, debug overlays for
dimensions and labels, instanced batches for repeated shapes such as
structural frames, and the screenshot harness for P01.7's baselines.
Scenarios describe the crop's rows and columns today, but not the greenhouse
around it.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P01.1 | `feat(world): define the greenhouse's origin, axes and bounds` | Done ([#28](https://github.com/AndreyBesedin/greenhouse-open/pull/28)) |
| P01.2 | `feat(greenhouse): generate the floor and a rectangular envelope` | Done ([#29](https://github.com/AndreyBesedin/greenhouse-open/pull/29)) |
| P01.3 | `feat(greenhouse): add pitched roof geometry` | Done ([#30](https://github.com/AndreyBesedin/greenhouse-open/pull/30)) |
| P01.4 | `feat(greenhouse): add bays and repeated structural frames` | Planned |
| P01.5 | `feat(envelope): add doors, vents and configurable openings` | Planned |
| P01.6 | `feat(materials): distinguish envelope semantics visually` | Planned |
| P01.7 | `test(visual): add greenhouse geometry QA snapshots` | Planned |

### P01.1: Greenhouse origin, axes and bounds

Document where the greenhouse sits in the world, and where its own origin and
axes are. Add a greenhouse bounding-box entity, and label its dimensions in
debug mode. Visible result: a transparent bounding volume with its width,
length and height labelled. Tests: known points map to the expected
positions, and the axes are labelled in the view.

As implemented (see [decision 0016](../decisions/0016-the-greenhouse-has-its-own-frame.md)):

- The greenhouse's frame has its origin at a floor corner, x along its
  length, y across its width and z up. An `Envelope`
  (`greenhouse_sim.world.envelope`) holds the transform that places that
  frame in the world, and the greenhouse's length, width and height. Every
  scenario declares one: gh_001 is 8 x 9.6 x 4.5 m, gh_002 4 x 3.2 x 4 m, and
  gh_demo 4 x 6.4 x 4 m.
- Geometry gains a `box` shape, and the scene a `GREENHOUSE_BOUNDS` entity
  showing the enclosed space. The scene schema moves to version 2, since an
  older viewer refuses the new kind and shape.
- The viewer draws the bounds as a see-through box with drawn edges. Its
  faces never take a click, so plants and ground inside stay selectable;
  its edges select it.
- A "Dimensions and axis labels" option labels the greenhouse's length,
  width and height along its edges, and the world's x, y and z.
- Tests:
  - Python: rotations and transforms move known points correctly. The
    corners of a greenhouse placed 100 m away and turned a quarter land
    where they should. An envelope without room is refused. Every
    scenario's ground and plants lie inside its greenhouse. The bounds
    entity stands on the middle of the floor, and follows a greenhouse
    placed elsewhere.
  - Viewer: the dimensions and axis labels, measured from the floor corner,
    turn with a turned greenhouse, and never change the scene. A browser
    test labels the dimensions, selects the bounds by an edge, and clicks
    through its faces to the ground.

### P01.2: Floor and rectangular envelope

A floor and side and end walls, of configurable length and width, each
surface with a semantic identifier. Visible result: an empty glasshouse box
with visible frame edges, which the camera can enter. Tests: changing the
dimensions in a scenario's configuration changes the geometry accordingly.

As implemented (see [decision 0017](../decisions/0017-envelope-surfaces-face-into-the-greenhouse.md)):

- `Envelope.surfaces()` generates the floor and four walls in the
  greenhouse's frame, each a rectangle with an identifier and a category,
  facing into the greenhouse. `surfaces_in_world()` places them with the
  greenhouse's origin. Walls are named as seen from the origin, looking
  along the length: `side_wall_right` (y = 0), `side_wall_left`,
  `end_wall_front` (x = 0) and `end_wall_back`.
- The scene shows them as `FLOOR` and `WALL` entities in place of the
  provisional ground, so the scene schema moves to version 3.
- The viewer draws the floor like the ground before it, and the walls as
  see-through glass framed by their edges. Clicks pass through the glass
  to what the walls enclose, and a wall's edges select it. The bounds,
  which now lie on the walls, are drawn only with the dimensions, as an
  outline that takes no clicks.
- Tests:
  - Python: one floor and four walls, with their names. The floor covers the
    footprint, and each wall stands on one of its edges up to the height.
    Every surface faces into the greenhouse. Every shared edge is shared by
    exactly two surfaces, with the four top edges open until the roof. The
    surfaces follow the envelope's dimensions, for a small house and a
    60 by 32 m one, and a placed greenhouse places them. A wall turned to
    face outwards, or a side wall a metre short, fails these tests.
  - Browser: a click through the glass reaches the floor; from above, the
    right side wall is selected by its top edge, with its size and position.

### P01.3: Pitched roof

Eave height, ridge height or roof pitch, roof panels and the gutter lines.
Visible result: a recognisable greenhouse profile replaces the box. Tests:
the cross-section's dimensions match the configuration.

As implemented:

- The envelope's height becomes an `eave_height` and a `ridge_height`; a
  ridge below the eaves is refused, and one level with them makes a flat
  roof. `roof_pitch` gives the slope. The scenarios' greenhouses now have
  eaves at 3 to 3.5 m and ridges at 3.65 to 5.4 m.
- The side walls rise to the eaves, the end walls are gables up to the
  ridge (a new `polygon` shape), and two roof slopes meet at the ridge,
  above the middle of the width. Each surface states its own axes
  (`Quaternion.from_axes`), its front facing into the greenhouse. A gutter
  runs along each eave (`Envelope.gutters()`).
- The scene adds `ROOF` and `GUTTER` entities, so its schema moves to
  version 4. The viewer draws the roof as glass, and gutters as channels
  with their top at the eaves.
- With the envelope closed, every edge is shared by two surfaces, so a
  wall can no longer be told by its edge. Glass is picked by the click
  instead, but only where nothing solid lies behind it: a click through the
  glass still reaches the plants and floor inside.
- Tests:
  - Python: the envelope's seven surfaces each have the corners the
    configuration gives them. The gable, the greenhouse's cross-section,
    has the eaves on both sides and the ridge above the middle, at the
    configured heights and pitch. Every surface faces in, and every edge is
    shared by exactly two surfaces, for a pitched roof and a flat one. A
    roof slope turned outwards, or a gable without its ridge corner, fails
    them. Gutters run along the eaves, and stand there in the scene.
  - Viewer: glass yields to a solid entity behind it, and is picked with
    nothing behind; a gable's bounds follow its corners. A browser test
    picks the back gable from the side view, and the floor through the
    glass.

### P01.4: Bays and repeated structural frames

Bay spacing, repeated posts and rafters, several spans, and frames drawn
instanced. Visible result: a greenhouse of several spans and bays, with a
realistic structural rhythm. Tests: changing the bay count gives the expected
number of frames, without coordinates drifting along the house.

### P01.5: Doors, vents and configurable openings

Semantic openings with an open fraction or angle, with a roof vent and a side
vent as examples. Visible result: a slider opens a roof vent in the view.
Tests: an opening exposes the expected aperture area at the boundary.

### P01.6: Envelope semantics, visually

Translucent glazing, an opaque foundation and floor, and structural members,
with a debug mode that colours each boundary category distinctly. Visible
result: the normal mode looks like a greenhouse, and the debug mode shows
each category in its own colour. Tests: every envelope polygon has a
semantic category.

### P01.7: Greenhouse geometry QA snapshots

Four fixed views of a canonical greenhouse: outside isometric, inside along
an aisle, top, and a debug section. Visible result: four stable baseline
screenshots, compared as P00.7's are.

## Final QA: `greenhouse-shell`

Change the length, width, number of spans, bay spacing, ridge and eave
heights and vent opening, and check that there are no gaps or inverted
surfaces, that the physical dimensions are right, that the camera can enter
the greenhouse, that the debug colours match each surface's semantics, and
that the screenshots stay deterministic.

## Acceptance criteria

- [ ] A configurable greenhouse shell exists as semantic geometry, not only
  as meshes.
- [ ] Openings can later become airflow boundaries.
- [ ] World dimensions are physically meaningful and inspectable.
- [ ] The renderer stays responsive at representative commercial
  dimensions.

## Later

- Setting a greenhouse up in the viewer: an editor that changes its
  description through the local API. P01 keeps the description in one
  validated model so that this needs no change to the geometry.
