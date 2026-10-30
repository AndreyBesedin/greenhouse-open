# Add a plant model

The crop is one part of the run, and a new plant model is a rung of it
([decision 0035](../decisions/0035-one-simulator-the-run-every-part-on-a-ladder-of-fidelity.md)),
chosen by a scenario's manifest from the registry
([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)).
Its ladder today:

- **the simple daily model** (`greenhouse_sim/greenhouse_sim/biology/tomato/simple/`),
  a rung as `SimpleRung` (`greenhouse_sim/greenhouse_sim/core/simple_crop.py`);
- **the organ-level tomato** (`greenhouse_sim/greenhouse_sim/biology/tomato/organ/`),
  a rung as `OrganRung` (`greenhouse_sim/greenhouse_sim/core/crop.py`).

The run drives either through `RunCrop` (`greenhouse_sim/greenhouse_sim/core/crop.py`),
which `greenhouse_sim/greenhouse_sim/services/crop.py` builds with the rung
of the model a scenario's rows grow.

**How the crop's moments are worked out:** a day at a time, the step of
every model grown plant by plant. At each midnight, every plant lives the
day that just ended in a `LocalEnvironment`
(`greenhouse_sim/greenhouse_sim/biology/plant/environment.py`,
[decision 0024](../decisions/0024-plants-take-their-environment-a-day-at-a-time.md)):
the house's mean temperature and CO₂ through that day, its own day's light
integral, and its water. Then the next day's crop work starts: a harvest
round, then a lowering round. Between two midnights, the crop is as at the
last ([decision 0064](../decisions/0064-a-runs-crop-steps-at-its-models-step-not-the-runs-day.md)):
the viewer, a plant's panel and the walk read it there
(`CropSteps.at`, `greenhouse_sim/greenhouse_sim/core/crop_steps.py`).

A rung keeps the crop's contract, `CropRung`
(`greenhouse_sim/greenhouse_sim/biology/crop_contract.py`): its plants start,
live their days and take their crop work without regard to one another, the
same every time, and survive a JSON round trip. A scenario's rows name the
model (`RowCrop.crop_model`, `greenhouse_sim/greenhouse_sim/scenarios/installation.py`,
[decision 0050](../decisions/0050-an-installation-is-the-house-part-of-a-scenario.md)),
and its manifest gives that model's parameters in its `models.crop` section.

This recipe is for a model of single plants. A model that grows a crop per
square metre of ground, with no plants of its own, as the published canopy
models do, keeps an area-based contract of its own beside `CropRung`
([decision 0062](../decisions/0062-a-crop-model-declares-its-scope-drivers-outputs-and-capabilities.md)):
`AreaRung` (`greenhouse_sim/greenhouse_sim/biology/area_contract.py`), on
a scope with its areas, driven through a driver profile
(`greenhouse_sim/greenhouse_sim/core/drivers.py`). Its rules, and those
of its step:

- **Its step** (`step_s`, [decision 0064](../decisions/0064-a-runs-crop-steps-at-its-models-step-not-the-runs-day.md)):
  a whole number of its profile's spans that divides a day, an hour or
  more with `house_hours`. A model whose state moves within a day takes a
  step shorter than a day; between two steps, the run shows it as at the
  earlier.
- **A step lived** (`live_step`): given its step's course (`StepCourse`),
  its drivers hour by hour from the step's start, it returns its canopy
  once it has lived it, the same every time, whatever other scopes grow
  beside it.
- **Its tests:** its rung added to `AREA_RUNGS` in
  `greenhouse_sim/tests/test_area_crop.py`, which holds every area model
  to the contract's rules at its own step.

## Steps

1. **The model's package:** a crop of its own under
   `greenhouse_sim/greenhouse_sim/biology/`, built on the generic plant
   (`greenhouse_sim/greenhouse_sim/biology/plant/`: organs, seeds, growth
   curves, environment, variation) without importing the tomato
   ([decision 0025](../decisions/0025-shared-vocabulary-in-a-domain-package-and-a-generic-plant.md)),
   its numbers in its own `parameters.py`. A tomato of another kind goes
   under `greenhouse_sim/greenhouse_sim/biology/tomato/`.
2. **Its day** takes a `LocalEnvironment`, and every draw comes from the
   plant's seed (`greenhouse_sim/greenhouse_sim/biology/plant/seeds.py`).
3. **Its rung,** beside `OrganRung` and `SimpleRung`, keeping `CropRung`:
   its plant, a pydantic model (its `plant_type`); a plant transplanted from
   its identifier and the scenario's seed; a day lived; a crop action
   carried out, or refused, saying why; its crown; and how many events its
   history holds (`recorded`), none if it keeps none. A scenario's crop work
   gives every model a harvest round and a lowering round, whatever crop
   actions of a plan it takes, so a rung carries those out at least.
4. **Its choice:** a member of `CropModel` in
   `greenhouse_sim/greenhouse_sim/domain/crop.py`, which a row names; its
   parameter model in `greenhouse_sim/greenhouse_sim/scenarios/crop_parameters.py`,
   with its `kind` the model's name, added to `ScenarioConfig.crop`'s union
   (`greenhouse_sim/greenhouse_sim/scenarios/config.py`); and its entry in
   the registry (`greenhouse_sim/greenhouse_sim/scenarios/registry.py`), a
   `Model` of `Part.CROP` under `MODELS`, with its parameter model, the
   configuration's field that holds them (`crop`) and its version.
5. **Its registration for the services**
   ([decisions 0055](../decisions/0055-a-model-is-registered-with-all-that-tells-it-apart.md)
   and 0062), under the same name in `CROP_MODELS`
   (`greenhouse_sim/greenhouse_sim/services/crop_models.py`), a
   `CropRegistration` of what the model declares:
   - **its state:** its state model, added to `CropModelState`, and what no
     run of it reaches in a checkpoint (`implausible`);
   - **its plants** (`plants`, a `PlantAdapter`): its rung, built from the
     scenario; how its plants are drawn (`drawn`); how a walk measures a
     plant (`measured`) and what a harvest round picked from one
     (`picked`); and what a replay reads beside a day's digest (`probed`);
   - **the run's own crop actions it takes** (`crop_actions`, a
     `CropActions` of their kinds), or `None` if it takes none. The gateway
     and the run route a plan's crop actions by those kinds, and refuse
     the others, naming the model.

   No service branches on a model's name, nor asks which model it holds:
   the crop's scene before and during a run, the plants' light,
   checkpoints, the crop log, the ground truth, the replay and the gateway
   ask the registration, and `greenhouse_sim/tests/test_crop_models.py`
   fails if a service names a model's rung. A plant's structure is the
   organ crop's alone: the plant route answers a crop whose rung declares
   organ plants (`CropRung.plant_type`).
6. **Its scene:** `drawn` gives its plants' entities. `crop_entities`
   (`greenhouse_sim/greenhouse_sim/scene/plants.py`) draws the tomato's
   organs, and `simple_plant_entities`
   (`greenhouse_sim/greenhouse_sim/scene/snapshot.py`) a simple plant. A new
   organ is a new entity kind and a renderer, as
   [add a device](add-a-device.md) describes for equipment.
7. **Its tests:** its rung added to `RUNGS` in
   `greenhouse_sim/tests/test_crop_rungs.py`, which holds every rung to the
   contract's rules; its registration held by
   `greenhouse_sim/tests/test_crop_models.py`, as every registration is;
   its numbers pinned, as `test_the_simple_rung_keeps_its_numbers` pins the
   simple crop's; and the run's coupling as
   `greenhouse_sim/tests/test_run_crop.py` and
   `greenhouse_sim/tests/test_run_simple_crop.py` check it.
8. **Its sources:** each equation and parameter from a cited source,
   ideally with a DOI, its units and range, its validation against
   published data, and any heuristic labelled as one (AGENTS.md,
   section 5).

## Generated files

```bash
uv run python greenhouse_sim/tests/test_published_schemas.py --update   # a new crop model in the manifests' schema
uv run python greenhouse_sim/tests/test_scene_schema.py --update        # new entity kinds
cd greenhouse_sim/web && npm run generate
```

A change to the tomato itself moves `greenhouse_sim/tests/golden/plant_lab.json`
(`greenhouse_sim/tests/test_plant_regression.py --update`), and, for the
reference greenhouse, its replay, opening day and views
(`greenhouse_sim/tests/test_replay.py`, `greenhouse_sim/tests/test_opening_day.py`,
`greenhouse_sim/tests/test_reference_qa.py`, each with `--update`).

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_crop_rungs.py greenhouse_sim/tests/test_crop_models.py \
  greenhouse_sim/tests/test_model_registry.py greenhouse_sim/tests/test_run_crop.py \
  greenhouse_sim/tests/test_run_simple_crop.py greenhouse_sim/tests/test_run_checkpoints.py \
  greenhouse_sim/tests/test_crop_log.py greenhouse_sim/tests/test_replay.py \
  greenhouse_sim/tests/test_domain.py greenhouse_sim/tests/test_subpackage_imports.py
uv run check --fast
uv run browser-tests e2e/crop.spec.ts
```

## What else to know

- **A model's version** (`version` in its registry entry,
  `greenhouse_sim/greenhouse_sim/scenarios/registry.py`) goes up by one
  whenever its numbers change for the same parameters: a run's identity
  covers it (P14.2), so its runs become other runs and a checkpoint made
  with the version before is refused.
- **Where a model's parameters live:** in a parameter model of its own,
  never as flat fields of the scenario's configuration. A crop model's are
  in `greenhouse_sim/greenhouse_sim/scenarios/crop_parameters.py`, told
  apart by their `kind`, the model's name, and the configuration holds
  those of the model its rows grow as its `crop`. A manifest gives them in
  its `models.crop` section, checked by that parameter model.
- **A parameter a model no longer has** is named in its registry entry's
  `retired` and dropped by its parameter model's before-validator, so that
  a manifest, a checkpoint or a stored configuration written before still
  reads; any other parameter it does not have is refused. The simple
  crop's four settings of the engine's day are retired so
  (`crop_parameters.RETIRED`).
- **The consumer's records** (`greenhouse_sim/greenhouse_sim/services/crop_log.py`)
  and the ground truth (`greenhouse_sim/greenhouse_sim/ground_truth.py`)
  read a plant as its registration measures it (`Measured`: its fruits,
  the ripe ones and their mass, its height) and its harvests as `picked`
  counts them. A crop of another kind says what it records.
