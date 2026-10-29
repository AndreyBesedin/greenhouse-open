# 0062: A crop model declares its scope, drivers, outputs and capabilities

**Status:** Proposed
**Date:** 2026-10-29

## Context

Decision 0060 makes two published tomato models crop models of the run:
Reduced-State TOMGRO and Vanthoor's model as Katzin simplified it. Both
grow a crop per unit of ground area, with no single plants, organs or
geometry. The run's crop part was built for single plants, and its
integration assumes them throughout:

- **The contract** (`biology/crop_contract.py`, `CropRung`) starts a plant
  by its identifier, lives it a day at a time, carries crop work out on it
  and places its crown, from which the plants' light is worked out.
- **The run** (`core/crop.py`, `RunCrop`) gives each plant its day
  (`LocalEnvironment`: the day's mean air temperature, the PAR its crown
  received, the CO₂), and keeps checkpoints, crop work and replay by the
  day.
- **What reads a crop model goes plant by plant:** its scene, the walk's
  observations, the ground truth, harvest events, the plants' light,
  checkpoints, the timeline, the greenhouse a consumer is described. The
  registration (`services/crop_models.py`, `CropRegistration`) is per plant
  in every field but its state, and its callers ask which model it is
  (`services.crop.is_organ`).
- **The air does not answer the crop,** for any model.

The first two published models will not be the last. What today's code
cannot do is not a property of crop models: a model grown by area may
prune, thin, harvest on a schedule, transpire, take up CO₂ or shade its
neighbours. The architecture is designed for the models to come, and the
code changes to meet it.

## Decision

- **Today's limits are named, not laws.** A simplification the first
  integration needs is a named, versioned integration profile or a declared
  capability, with its limits and its tests, never a rule of the crop
  part. Where the infrastructure cannot do what the science needs, the
  infrastructure changes, in pull requests of their own.
- **Two representations, one integration.** A crop model represents single
  plants (the organ and simple models) or an area of crop (the two
  published models). Each keeps a physiology contract of its own: the
  per-plant one stays as it is, and the area-based one is new. Everything
  else the run does with a crop model goes one way for both: the registry
  and the manifest, checkpoints and replay, the routing of actions, the
  scene, and what is observed and kept as truth. It goes by what the model
  declares, through typed adapters, never by asking which model it is.
- **A crop instance is a model on a spatial scope.** What the run grows is
  an instance: a model, its parameters and its state, on a spatial scope (a
  row, a bed, a growing zone, a compartment, the house), with that scope's
  geometry. The model and its scope are apart: the first implementation may
  give each row an instance, and a zone or a compartment is as possible.
  One generalised crop part keeps instances of both representations; no
  second run is kept beside the first.
- **Each model's reference area is its own.** A model declares the area
  its quantities are per, and the density it assumes or takes: GreenLight's
  leaf area index is per m² of greenhouse floor, for instance. A scope's
  areas are kept apart (its floor, its cultivated area, its beds, net of
  paths and paired rows' gaps), and every conversion between a scope and a
  model's basis is explicit, recorded and tested: the same crop on two
  layouts of one density, with paths or paired rows or other spacings,
  conserves its mass and its area. A published parameter set is never
  rescaled silently: one used on another basis or density is an adaptation,
  said to be so, and no longer the reproduced model.
- **Drivers through versioned profiles.** A model declares its drivers: each
  quantity, its unit, whether it is a moment's value or a mean, its
  resolution and how it is interpolated. A driver profile, named and
  versioned, says how the run provides them, and what it substitutes. The
  first, for the run as it is: the whole house's air, hour by hour, as each
  plant reads its day's mean today, its temperature standing for the
  canopy's; the PAR above the canopy; the CO₂. Its effect on a model's
  results, against the reference's own resolution and against a canopy
  temperature, is measured and reported. Driving a reproduced model through
  a profile is an integration, not the reproduction: the reproduction's
  forcing stays its own (decision 0060, milestone A).
- **Light: incident and absorbed apart.** The run gives the light above a
  scope, from the sun and the lamps; how much the canopy absorbs, through
  its leaf area, extinction and reflection, is the model's. A canopy's
  interception of the house's light, and competition between scopes, are
  capability ports, for the models and the light model that support them;
  the first light adapter does without them, and says so.
- **Three kinds of output, kept apart:**
  - **latent state,** what the model holds (its pools, its leaf area): the
    run's, and the evaluation's truth, never a consumer's observation;
  - **measurements,** made by a versioned measurement model with its
    sampling, availability, delay, noise and bias, its spatial identity and
    units: a weighing of the harvest, a destructive sample, an instrument's
    reading. A perfect measurement is a research instrument, declared as
    one, never the default;
  - **estimates and forecasts,** inferences from measurements, records of
    their own (decision 0061).
  No latent quantity reaches the consumer interface because the model knows
  it.
- **Native quantities first.** Each model registers its outputs in its own
  quantities and units, on its own reference area: GreenLight's
  carbohydrate equivalents (mg CH₂O m⁻²), TOMGRO's dry masses. A dry or
  fresh yield is derived only by a named conversion, with its source and
  its uncertainty, and a quantity is never compared with another kind
  without one.
- **Capabilities declared, actions routed by them.** A model declares the
  interventions it represents (crop actions, harvest schedules, pruning,
  thinning, biomass removal, irrigation), and the run routes an action to
  the models that take it; one a model does not take is refused, saying
  why. Crop work is a capability too. The two published variants take none
  of the run's crop actions, their harvest their own rule's; that is said of
  them, not of every model grown by area.
- **Climate coupling as typed ports.** A model may declare fluxes it gives
  the air: transpiration and its latent heat, CO₂ taken up, radiation
  exchanged, each time-aligned and in its units, with conservation tests.
  The house taking them is a climate decision of its own. Until then the
  coupling is one-way, from the air to the crop, a declared profile, not a
  rule.
- **Drawn as what it is.** A model declares how it is drawn: organs, a plant
  proxy, or a canopy volume for an area, its height from its parameters and
  its density from its leaf area index, marked as a proxy, never drawn as
  plants it does not have.
- **Held to contract tests:** a per-plant test (`test_crop_rungs.py`) and an
  area-based one, each holding a model to being deterministic, leaving the
  state it is given as it was, keeping its instance's identity and
  surviving a JSON round trip; the area-based one also to the conversions'
  conservation across layouts.
- **Results of integration are predictions** until a model is validated on
  measured data (decision 0060, milestone C), and are labelled so.

## Consequences

- **The crop part is generalised,** over instances and the capabilities
  they declare: the registration's per-plant fields become typed adapters,
  and the callers that ask which model they hold ask what it declares. The
  simple and organ models declare what they do today, and their runs do not
  change.
- **Changes beyond the crop part,** each in a pull request of its own: the
  scope's geometry and areas; the driver profiles; the light above a scope;
  the measurement models and the observation types they make; the scene's
  proxies; new `CropModel` members and the schemas they regenerate; and
  checkpoints, the timeline and the gateway, which name instances where
  they named plants.
- **A climate-coupling decision** comes before any model's fluxes reach the
  house's air.
- **What it gives up:** a model that declares nothing costs the
  integration little; one that declares much is integrated as far as its
  declarations go, and no further.
- **Worth revisiting:** if a published model needs a coupling, a scope or a
  driver the declarations cannot express.
