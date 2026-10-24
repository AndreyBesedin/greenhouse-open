# Add a plant model

The crop is one part of the run, and a new plant model is a rung of it,
never a model of the engine's day ([decision 0035](../decisions/0035-one-simulator-the-run-every-part-on-a-ladder-of-fidelity.md)).
Its ladder today:

- **the simple daily model** (`greenhouse_sim/greenhouse_sim/biology/tomato/simple/`),
  which the engine's day still drives, through `PlantModel`
  (`greenhouse_sim/greenhouse_sim/biology/contract.py`);
- **the organ-level tomato** (`greenhouse_sim/greenhouse_sim/biology/tomato/organ/`),
  which the run drives through `RunCrop` (`greenhouse_sim/greenhouse_sim/core/crop.py`),
  built by `greenhouse_sim/greenhouse_sim/services/crop.py`.

**How the crop's moments are worked out:** a day at a time. At each
midnight, every plant lives the day that just ended in a `LocalEnvironment`
(`greenhouse_sim/greenhouse_sim/biology/plant/environment.py`,
[decision 0024](../decisions/0024-plants-take-their-environment-a-day-at-a-time.md)):
the house's mean temperature and CO₂ through that day, its own day's light
integral, and its water. Then the next day's crop work starts: a harvest
round, then a lowering round.

`RunCrop` calls the tomato's functions by name, so the crop has no contract
of its own yet (`AUDIT.1` in the [repository audit](../audits/2026-10-13-repository-audit.md)),
and how a scenario names its rung is not decided. The first model to add a
rung writes both, as the steps below say.

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
3. **The crop's contract,** in `greenhouse_sim/greenhouse_sim/biology/contract.py`
   beside `PlantModel`: what the run calls on the tomato today (a plant
   transplanted from its identifier and seed, a day lived, a harvest round,
   a lowering round, its stem's height), its plant a pydantic model that
   survives a JSON round trip. Then `RunCrop` takes the contract, in a
   pull request that changes no number.
4. **Its choice:** a member of `CropModel` in
   `greenhouse_sim/greenhouse_sim/domain/crop.py`, chosen by a manifest's
   `crop_model`, and every branch on `CropModel.ORGAN` handled, in the
   services (`greenhouse_sim/greenhouse_sim/services/crop.py`, its
   checkpoints, sunlight, crop log and replay) and in the viewer
   (`greenhouse_sim/web/src/plants/crop.ts`).
5. **Checkpoints** keep the tomato's plants: a model of another kind raises
   `CHECKPOINT_FORMAT` in `greenhouse_sim/greenhouse_sim/services/checkpoints.py`,
   with a migration for the checkpoints already kept.
6. **Its scene:** `crop_entities` (`greenhouse_sim/greenhouse_sim/scene/plants.py`)
   draws the tomato's organs. A new organ is a new entity kind and a
   renderer, as [add a device](add-a-device.md) describes for equipment.
7. **Its tests:** a conformance test over every implementation of the
   contract, with the rules `greenhouse_sim/tests/test_model_contracts.py`
   holds the engine's models to (one plant per identifier, the same plants
   for the same seed, its arguments left as they were, each plant apart
   from the others, a JSON round trip), and the run's coupling as
   `greenhouse_sim/tests/test_run_crop.py` checks it.
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
uv run pytest greenhouse_sim/tests/test_run_crop.py greenhouse_sim/tests/test_model_contracts.py \
  greenhouse_sim/tests/test_checkpoints.py greenhouse_sim/tests/test_run_checkpoints.py \
  greenhouse_sim/tests/test_crop_log.py greenhouse_sim/tests/test_replay.py \
  greenhouse_sim/tests/test_domain.py greenhouse_sim/tests/test_subpackage_imports.py
uv run check --fast
uv run browser-tests e2e/crop.spec.ts
```

## What else to know

- **Nothing new goes on the engine's day** (`greenhouse_sim/greenhouse_sim/core/engine.py`):
  it only takes fixes.
- **Where a model's parameters live:** in the model's own `parameters.py`,
  never as flat fields of the scenario's configuration. A manifest gives a
  crop model's parameters in its `models.crop` section, checked by its
  parameter model in `greenhouse_sim/greenhouse_sim/scenarios/registry.py`
  ([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md));
  the registry's crop models are the simple and the organ crop until
  P14.3 makes the crop a part the run chooses by it.
- **The consumer's records** (`greenhouse_sim/greenhouse_sim/services/crop_log.py`)
  count fruit and ripe mass as the tomato's organs have them: a crop of
  another kind says what it records.
