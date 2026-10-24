# Add a plant model

The crop is one part of the run, and a new plant model is a rung of it,
never a model of the engine's day ([decision 0035](../decisions/0035-one-simulator-the-run-every-part-on-a-ladder-of-fidelity.md)).
Its ladder today:

- **the simple daily model** (`greenhouse_sim/greenhouse_sim/biology/tomato/simple/`),
  a rung as `SimpleRung` (`greenhouse_sim/greenhouse_sim/core/simple_crop.py`),
  which the engine's day also drives, through `PlantModel`
  (`greenhouse_sim/greenhouse_sim/biology/contract.py`), until the engine goes;
- **the organ-level tomato** (`greenhouse_sim/greenhouse_sim/biology/tomato/organ/`),
  a rung as `OrganRung` (`greenhouse_sim/greenhouse_sim/core/crop.py`).

The run drives either through `RunCrop` (`greenhouse_sim/greenhouse_sim/core/crop.py`),
which `greenhouse_sim/greenhouse_sim/services/crop.py` builds with the rung
of the model a scenario's rows grow.

**How the crop's moments are worked out:** a day at a time. At each
midnight, every plant lives the day that just ended in a `LocalEnvironment`
(`greenhouse_sim/greenhouse_sim/biology/plant/environment.py`,
[decision 0024](../decisions/0024-plants-take-their-environment-a-day-at-a-time.md)):
the house's mean temperature and CO₂ through that day, its own day's light
integral, and its water. Then the next day's crop work starts: a harvest
round, then a lowering round.

A rung keeps the crop's contract, `CropRung`
(`greenhouse_sim/greenhouse_sim/biology/crop_contract.py`): its plants start,
live their days and take their crop work without regard to one another, the
same every time, and survive a JSON round trip. A scenario names its rung by
its rows' crop model, with that model's parameters in its manifest's
`models.crop` section ([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)).

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
   carried out, or refused, saying why (a harvest round and a lowering
   round at least, which a scenario's crop work gives); and its crown.
4. **Its choice:** a member of `CropModel` in
   `greenhouse_sim/greenhouse_sim/domain/crop.py`, which a row names; its
   parameter model in `greenhouse_sim/greenhouse_sim/scenarios/crop_parameters.py`,
   added to `ScenarioConfig.crop`'s union and registered with its version in
   `greenhouse_sim/greenhouse_sim/scenarios/registry.py`.
5. **Its registration for the services** ([decision 0055](../decisions/0055-a-model-is-registered-with-all-that-tells-it-apart.md)),
   under the same name in `CROP_MODELS`
   (`greenhouse_sim/greenhouse_sim/services/crop_models.py`): its rung,
   built from the scenario; its state model, added to `CropModelState`, and
   what no run of it reaches in a checkpoint (`implausible`); how its plants
   are drawn (`drawn`); how a walk measures a plant (`measured`) and what a
   harvest round picked from one (`picked`); and what a replay reads beside
   a day's digest (`probed`). No service branches on a model's name: the
   crop's scene before and during a run, the plants' light, checkpoints,
   the crop log and the replay ask the registration. A plant's structure
   and the run's own crop actions are the organ crop's alone.
6. **Its scene:** `crop_entities` (`greenhouse_sim/greenhouse_sim/scene/plants.py`)
   draws the tomato's organs. A new organ is a new entity kind and a
   renderer, as [add a device](add-a-device.md) describes for equipment.
7. **Its tests:** its rung added to `RUNGS` in
   `greenhouse_sim/tests/test_crop_rungs.py`, which holds every rung to the
   contract's rules; its registration held by
   `greenhouse_sim/tests/test_crop_models.py`, as every registration is;
   and the run's coupling as
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
uv run pytest greenhouse_sim/tests/test_crop_rungs.py greenhouse_sim/tests/test_run_crop.py \
  greenhouse_sim/tests/test_run_simple_crop.py greenhouse_sim/tests/test_model_contracts.py \
  greenhouse_sim/tests/test_checkpoints.py greenhouse_sim/tests/test_run_checkpoints.py \
  greenhouse_sim/tests/test_crop_log.py greenhouse_sim/tests/test_replay.py \
  greenhouse_sim/tests/test_domain.py greenhouse_sim/tests/test_subpackage_imports.py
uv run check --fast
uv run browser-tests e2e/crop.spec.ts
```

## What else to know

- **A model's version** (`version` in its registration,
  `greenhouse_sim/greenhouse_sim/scenarios/registry.py`) goes up by one
  whenever its numbers change for the same parameters: a run's identity
  covers it (P14.2), so its runs become other runs and a checkpoint made
  with the version before is refused.
- **Nothing new goes on the engine's day** (`greenhouse_sim/greenhouse_sim/core/engine.py`):
  it only takes fixes.
- **Where a model's parameters live:** in a parameter model of its own,
  never as flat fields of the scenario's configuration. A crop model's are
  in `greenhouse_sim/greenhouse_sim/scenarios/crop_parameters.py`, told
  apart by their `kind`, the model's name, and the configuration holds
  those of the model its rows grow as its `crop`. A manifest gives them in
  its `models.crop` section, checked by that parameter model, which
  `greenhouse_sim/greenhouse_sim/scenarios/registry.py` registers
  ([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)).
- **The consumer's records** (`greenhouse_sim/greenhouse_sim/services/crop_log.py`)
  count fruit and ripe mass as the tomato's organs have them: a crop of
  another kind says what it records.
