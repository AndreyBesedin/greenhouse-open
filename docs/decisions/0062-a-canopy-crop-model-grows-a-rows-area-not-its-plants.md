# 0062: A canopy crop model grows a row's area, not its plants

**Status:** Proposed
**Date:** 2026-10-29

## Context

Decision 0060 makes two published tomato models crop models of the run:
Reduced-State TOMGRO and Vanthoor's model as Katzin simplified it. Both
grow a canopy per square metre of ground: biomass, leaf area and fruit
per m², with no individual plants, organs or geometry. The run's crop part
is built for individual plants:

- **The contract** (`biology/crop_contract.py`, `CropRung`) starts a plant
  by its identifier, lives it a day at a time, carries crop work out on it
  (`carry_out`), and says where its crown is (`crown`), from which the
  plants' light is worked out.
- **The run** (`core/crop.py`, `RunCrop`) keeps the plants and gives each
  its day (`LocalEnvironment`: the day's mean air temperature, the PAR its
  crown received that day, the CO₂). The day is its unit of work: the days
  lived, crop work (`DayWork`), checkpoints and replay digests are kept by
  the day.
- **What reads a crop model** goes plant by plant: its scene, the walk's
  observations and the ground truth (`Measured`), harvest events
  (`picked`), the plants' light (each plant's crown), checkpoints (each
  plant, in the order of `plant_ids`), the timeline, and the greenhouse a
  consumer is described. The registry (decisions 0054 and 0055) registers
  a crop model with what it gives these (`services/crop_models.py`,
  `CropRegistration`), and rows name the crop they grow
  (`RowCrop.crop_model`, decision 0050).
- **Crop work is every model's:** a scenario's harvest and lowering rounds
  (`CropWork`) are carried out on every plant, whatever model grows it.
- **No area is kept:** neither the house's floor area nor a crop's planted
  area is stored. Heat is given per m² of floor; a plant's light per m² of
  its crown's top. The packaged scenarios' plants per m² differ threefold
  between their floor and their rows' cells.
- **The air does not answer the crop:** no transpiration and no CO₂
  uptake reach the house's air, for any model.

Fitting a canopy model to that contract would mean inventing plants,
organs and crowns it does not have. Changing the contract for every model
would change the simple and organ models to fit two others.

## Decision

- **A canopy model is a crop model of its own kind,** beside the per-plant
  ones, with a contract of its own (a canopy rung). `CropRung` is not
  widened, and the simple and organ models do not change.
- **Its unit is a row's area.** Each row the canopy model grows is one
  unit, known by the row (`row_1`, ...), its draws seeded by it and its
  units kept in the rows' order. Its area is the ground the row takes,
  its length by its spacing, from the layout's crop rows; its density is
  the row's planting positions over that area, so that a per-plant and a
  canopy model agree on one installation. Its state is per m² of that
  area, kept per unit. "Per m²" means per m² of crop area wherever a canopy
  model says it, apart from the floor's, by which heat is given.
- **Rows name it,** as they name every crop model (decision 0050): each
  canopy model is a member of `CropModel`, which regenerates the
  installation's, the builder's and the scenario's schemas, and the
  viewer's types made from them.
- **The day stays the unit of work.** The run gives a unit its day as it
  gives a plant its day, and its course besides: hour by hour, the air's
  temperature, the PAR above the canopy and the CO₂. Checkpoints, crop work
  and replay keep their shape; the days lived grow by about 24 values per
  unit and day. A model that needs a finer step integrates within the day
  from the hours it is given.
- **Light above the canopy, absorbed by the model.** The sun's part gives
  each unit the PAR above it, along the row at the canopy's height, which
  a canopy model's parameters give, since neither model grows a height.
  How much of it the canopy absorbs, through its leaf area, extinction and
  reflection, is the model's. Incident and absorbed PAR are named apart
  wherever either appears. A canopy is not a crown: it shades nothing in
  the house's light.
- **Registered as the others are** (decision 0055): a registry entry with
  its parameters, version 1, and a published parameter set named as a
  field of the parameters, with its default; a registration with its
  state, which survives a JSON round trip as a new member of the crop
  part's state in checkpoints. Adding the models moves no pinned run.
- **Observed per m², or not at all.** What a canopy model can honestly
  give a consumer is per area: its leaf area index, its fruit's dry weight
  standing, and the dry weight it harvested, per m² of crop area. These
  are new observation types of the protocol, of the crop as a whole (its
  units' values weighted by their areas, with no plant named), with their
  truth from the model's state. The walk's per plant records (heights,
  fruit counts, ripe mass) and plants' harvest events are not produced for
  a canopy, and nothing per m² is mapped onto them. The greenhouse a
  consumer is described says its crop is grown by area, with its rows and
  their areas, and lists no plants.
- **No crop actions, no crop work:** a canopy model takes none of the
  run's crop actions, which are refused with their reason, as the simple
  model's are (`takes_crop_actions`, `runs.crop_moment_refusal`). A
  scenario whose rows grow a canopy model sets no crop work; one that does
  is refused, saying why. Its harvest is its own rule's, not a round.
- **Drawn as a proxy:** a row of a canopy model is drawn as a canopy
  volume, its height and density from its state, as an entity kind of its
  own that says it is a proxy, never as plants. That is a change to the
  scene's schema and the viewer's types.
- **One way, from the air to the crop,** as for every crop model now. The
  crop's transpiration and CO₂ uptake reaching the house's air are a
  climate decision of their own.
- **Held to a contract test:** as `test_crop_rungs.py` holds per-plant
  models, a canopy test holds each canopy model to being deterministic,
  leaving the state it is given as it was, keeping its unit's identity, and
  surviving a JSON round trip; and to growing the same per m² on two rows
  of the same density and course.

## Consequences

- **A crop part with two kinds of model:** the run keeps per-plant and
  canopy units side by side, generalised over a unit, or a canopy beside
  `RunCrop`; which, is settled in its implementation, with the tests above.
- **Changes beyond the crop part,** each named in its pull request: new
  `CropModel` members and the schemas they regenerate; observation types
  in the protocol, and the greenhouse description of a crop grown by area;
  the sun's PAR above a row; a scene entity for the proxy; the crop part's
  closed unions of states (`CropModelState`, a checkpoint's), which grow a
  member each; and checkpoints, the timeline and the gateway's targets,
  which name units where they named plants.
- **What stays per plant:** the plant inspector's route answers the organ
  model alone, as it does for the simple one.
- **A row grows one model:** mixed rows wait (P12.5 and P12.6).
- **What it does not give:** organ geometry, crop work, robots' tasks and
  the walk's per plant records stay the per-plant models'. A canopy model
  is for questions asked per m².
- **The canopy's temperature** is taken as the air's: the house has no
  canopy temperature. That is a difference from GreenLight, which works the
  canopy's energy balance, recorded with each comparison.
- **Worth revisiting:** if a canopy model needs the crop's feedback on the
  air to be right, or if a per-plant model needs per m² outputs.
