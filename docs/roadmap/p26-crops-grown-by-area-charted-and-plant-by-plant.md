# P26: Crops grown by area, charted and grown plant by plant

**Status:** proposed: the steps below, with
[decision 0083](../decisions/0083-a-crop-grown-by-area-is-charted-and-may-grow-on-each-plants-spot.md).
Part of the [simulator roadmap](README.md).

## Goal

A crop grown by area is seen as its model is read: its states over the
season, the house's with its rows' range, labelled as predictions, and not
as a volume over each row. Reduced-State TOMGRO may also grow on each
planting position's spot, each spot in its own light, so that the plants by
the walls and those in the middle grow apart as their light says. Each such
plant is drawn as a proxy from its state.

## Where it starts

- **Two models grown by area** run in the packaged `tomgro_house` and
  `vanthoor_house`, an instance on each of their four rows (decision 0062,
  P14.10). Their states are per m² of floor.
- **The scene draws each row as a canopy volume,** a proxy as dense as the
  light its leaves take (`scene/snapshot.py`, `canopy_entities`; the
  viewer's `scene/canopy.ts`). The models' quantities show only in the
  selected canopy's properties.
- **No route gives a crop grown by area's course.** `GET .../crop` gives
  the crop at one moment, as a scene. The crop keeps what it lived on at
  each step (`core/crop_steps.py`), so its states can be lived again day
  by day without the air or the light.
- **The viewer cannot tell how a crop is grown** but by its model's name:
  the scenario's summary gives `crop_model` alone.
- **A scope is a row** (`world/scopes.py`, `row_scopes`), and its light is
  read at each of its planting positions and averaged
  (`solar/scopes.py`, `ScopeLight`).

## When

Now, beside P24 and P25: it touches the crop's scopes and the viewer, which
neither of them changes.

## What stays stable

- **A crop grown by rows:** its run ids, checkpoints and replay digests.
  P26.1 changes what the scene draws, not what the run computes.
- **A crop grown plant by plant,** the organ and simple models, and its
  scene.
- **The two models' parameters,** used as published (decision 0062).

## Design

### A crop grown by area, charted (P26.1)

- **The model declares its charted quantities** in place of its drawing:
  each with a key, a name and a unit, and a reading of a state.
  - TOMGRO's are its five states: main stem nodes, leaf area index, and the
    dry weight above ground, of the fruit and of the mature fruit, in g m⁻².
  - Vanthoor's are its leaf area index, its carbohydrate buffer, leaf, stem,
    fruit and harvested fruit, in mg CH₂O m⁻², its temperature sum and its
    canopy's temperature over the last day.
  - Neither is converted into the other's quantities.
- **A route gives the course:** `GET /api/scenarios/{id}/area_crop`, asked
  as the crop is, with `&t=`. It answers, for each day from the first to
  the moment's:
  - each scope's values, the state at the start of the day;
  - the house's, the scopes' mean weighted by their area on the model's
    basis.
  A crop grown plant by plant is refused by name.
- **The scenario's summary says how its crop is grown,** by plants or by
  area.
- **The viewer charts it** in a panel of its own, for a crop grown by area
  only:
  - one chart a quantity, the house's line with the rows' least and most
    behind it, up to the moment shown;
  - the moment's value with the rows' range in words;
  - labelled as the model's predictions, per m² of its basis.
  It asks again only when the day changes.
- **The scene draws no canopy volume:** the snapshot's `CANOPY` kind goes,
  and its schema moves from 17 to 18.

### A plant's spot, a scope (P26.2)

- **A scope of a planting position,** named for it. Its cultivated ground
  is the position's, its pitch by its row's share of the spacing. Its floor
  is its share of the house's, as a row's is, by its cultivated ground.
- **The crop model's settings name its scope,** `row` by default or
  `plant`, in the manifest's `models.crop` and in the run's identity.
- **Its light is read at its own position,** at the canopy's height. That
  is the reading the rows' light already makes, not averaged along the row.
  Its air is the driver profile's, the whole house's hour by hour.
- **A packaged scenario,** `tomgro_plants`: the TOMGRO house, grown on its
  32 planting positions' spots.
- **The chart's band is the spots' range,** and it names the spot at each
  end.
- **Its limit test:** with every spot given its row's drivers, each spot's
  state is its row's, value for value, for both models.

### TOMGRO's plant proxy (P26.3)

- **At each planting position, the model's plant:** its spot's state
  divided by ρ, the plants per m² its parameters are for.
  - Its nodes along a stem, as tall as its nodes by the drawing's
    internode length.
  - Its leaves, their area its leaf area per plant.
  - Its fruit on trusses from its first fruiting node, ripe in the share of
    its mature fruit.
- **The drawing's settings** (internode length, nodes to a truss, a leaf's
  shape) are named as such, not taken for the model's.
- **Marked as a proxy,** its numbers as predictions. The chart says the
  layout's density beside ρ: `tomgro_house`'s 32 positions on 115 m² of
  floor stand for 0.28 plants per m², where gnvman's parameters are for 3.5.
- **Vanthoor's model has no proxy:** its states are carbohydrate pools,
  with no nodes and no fruit count. It is charted alone, on rows or on
  spots.

### What it leaves

- **Each spot's air from the grid:** a driver profile of its own.
- **Plant-to-plant variation of parameters:** a named variation, an
  adaptation of the published set.
- **Neighbours shading one another, spot by spot:** decision 0062's port
  for competition.
- **Vanthoor's model drawn as plants.**

## Steps

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P26.1 | **A crop grown by area, charted:** its model's charted quantities, the course's route, the summary's `crop_grown_by`, the viewer's panel, and the scene without its canopy volume (schema 18) | The TOMGRO and Vanthoor houses chart their course up to the moment shown; a day's values are the crop's at that day; a course to a day is the start of a course to a later one; no run id or digest moves | Proposed |
| P26.2 | **A plant's spot, a scope:** the `plant` scope, chosen by the crop model's settings and in the run's identity; each spot's light at its position; `tomgro_plants` packaged | Given its row's drivers, each spot's state is its row's, value for value; runs on rows keep their ids and digests; `tomgro_plants` runs its season, and its spots' spread from the walls to the middle is reported | Proposed |
| P26.3 | **TOMGRO's plant proxy:** drawn at each planting position from its state, per the model's plant, with the drawing's settings named | A proxy follows its state: taller with its nodes, its leaves by its leaf area, fruit from its first fruiting node and ripe in its mature fruit's share; it is marked as a proxy; a visual baseline holds it | Proposed |
| P26.4 | The QA scenario below, run and recorded | Each step passes in the browser | Proposed |

## QA scenario (proposed)

In the browser:
1. Open `tomgro_house`. The rows draw no canopy volume. The *Crop by area*
   panel charts its five states up to the moment shown, labelled as
   predictions per m² of floor. Move to day 60: each chart reaches it, and
   its values are the crop's then. Play within a day: nothing is asked
   again.
2. Open `vanthoor_house`: its own quantities, in carbohydrate equivalents,
   not TOMGRO's.
3. Open the reference greenhouse: no such panel, and its plants as before.
4. Open `tomgro_plants`: a proxy plant at each of its 32 positions. Those by
   the walls and those in the middle differ as the chart's band says. The
   chart names the layout's density beside ρ.
5. Select a proxy plant: its spot, its state and the plant it stands for,
   marked as a proxy.

## Open questions

- **The chart's quantities:** whether TOMGRO's dry matter above ground
  should be split by organ in the chart, as Vanthoor's carbohydrates are.
  The model's states hold only the total and the fruit, so a split would be
  derived.
