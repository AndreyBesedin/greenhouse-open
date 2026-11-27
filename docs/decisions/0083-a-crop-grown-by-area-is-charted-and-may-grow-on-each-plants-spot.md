# 0083: A crop grown by area is charted, and may grow on each plant's spot

**Status:** Proposed, with [P26](../roadmap/p26-crops-grown-by-area-charted-and-plant-by-plant.md)'s plan
**Date:** 2026-11-24

## Context

- **What the viewer shows of a crop grown by area.** Decision 0062 lets a
  model declare how it is drawn. A crop grown by area, Reduced-State TOMGRO
  or Vanthoor's model, is drawn as a canopy volume over each row: as tall as
  its parameters say, and as opaque as the share of the light its leaves
  take, marked as a proxy. Its quantities show only in the list of the
  selected entity's properties, at the moment shown.
- **That volume says little.** The rows of one house look alike. What the
  two models are read by, in their papers and in the reproductions, is
  their states over the season: the leaf area index, the dry matter or
  carbohydrates by organ, the fruit and its harvest. None of that is seen
  as a course, and none of it is compared from one row to another.
- **Both models are written for a stand.** Their states are per m² of
  floor. TOMGRO's equations are for its parameters' ρ plants per m², and
  its leaf area grows as ρ times a plant's. How much light the canopy takes
  is a stand's law, from its leaf area index.
- **The scope is apart from the model.** Decision 0062 makes a crop
  instance a model on a spatial scope, and the first scope is a row. The
  light above a scope is worked out at its planting positions, at its
  canopy's height (`solar.scopes.ScopeLight`). The light differs across a
  house, and most in a small one: the packaged houses see 44 to 58 % of
  their sky through their walls (#768). An instance per row averages that
  difference away along the row, and a plant by a wall grows like one in
  the middle.

## Decision

- **A crop grown by area is charted, not drawn.** The scene draws no
  instance of a model grown by area. The model declares the quantities it
  is charted by, each with its name and unit, in its own quantities and on
  its own basis (decision 0062's native quantities), and how each is read
  from a state. The viewer charts them day by day, up to the moment shown:
  the house's value, each scope's weighted by its area on the model's
  basis, with the scopes' least and most behind it. The chart is labelled
  as the model's predictions. This replaces "or a canopy volume for an
  area" in decision 0062's "Drawn as what it is", whose rule otherwise
  stands: a model declares how it is shown, and is never drawn as plants
  it does not have.
- **A plant's spot is a scope.** A model grown by area may grow on each
  planting position's spot rather than on each row. The spot's cultivated
  ground is the position's, its pitch by its row's share of the spacing,
  and its floor is its share of the house's, as a row's is today. Its
  instance's state is per m² of its model's basis, as every instance's is.
  Its totals are that state times the spot's area, so a crop grown on the
  spots of a row conserves what the row's would hold under the same
  drivers. The model, its step, its contract and its driver profile are
  unchanged.
- **Its drivers are its spot's.** The light above its canopy is read at
  its own position, as a row's is read at each of its positions and
  averaged. Its air is the driver profile's: under the whole house it is
  the same for every spot. A profile that gives each spot the grid's air
  at its cells is a profile of its own, named and versioned as decision
  0062 asks.
- **Chosen by the manifest, in the run's identity.** The crop model's
  settings name its scope: `row`, as today and by default, or `plant`. A
  run on another scope is another run, with another id. A run on rows
  keeps its id, its checkpoints and its digests.
- **Its limit, held by a test.** Given the same drivers at every spot,
  each spot's state is its row's, value for value: a crop grown by spot
  differs from one grown by row only by what its spots are given.
- **The stand's laws stay the model's.** A spot's canopy takes light by
  its own leaf area index, as if it were a stand of plants like it. How
  its neighbours shade it is the stand's, not worked out plant by plant:
  decision 0062's port for competition between scopes stays a port.
- **Published parameters stay as published.** No spot's parameters are
  varied. Varying them from plant to plant is an adaptation of the
  published set (decision 0062), and would be a named variation of its
  own.
- **A plant proxy, where the model's states give one.** A model grown on
  spots may declare a plant proxy, drawn at each planting position from
  its state, marked as a proxy, and its numbers as predictions. The proxy
  is the model's plant, its spot's state divided by the density its
  parameters are for (TOMGRO's ρ), not the spot's totals. Where the
  layout's density differs from the model's, the chart says both. TOMGRO's
  states give one: its main stem's nodes, its leaf area and its fruit and
  mature fruit, per plant. How long an internode is drawn, and how many
  nodes a truss takes, are the drawing's settings, named as such, not the
  model's. Vanthoor's states, carbohydrate pools with no nodes and no fruit
  count, give none: it is charted alone.

## Consequences

- **The scene's schema moves** as the canopy volume goes, and the
  scenario's summary says how its crop is grown, by plants or by area, so
  that the viewer charts a crop grown by area without asking which model
  it is. A crop grown by area's course is a route of its own.
- **Its cost is a crop's:** a spot is a scope like a row, its light read
  at the positions the rows' light already reads, and its state a few
  numbers. A checkpoint keeps an instance per spot.
- **What it adds is a spread:** how plants by the walls grow against
  those in the middle, through the light alone, which the run can then
  set beside the organ model's plants. That spread is a prediction, not
  validated on measured data (decision 0060, milestone C).
- **Worth revisiting** if the spread from light alone proves small
  against what plants are measured to differ by, or when a canopy model
  with its own geometry, which shades its neighbours, takes the place of
  the stand's law.
