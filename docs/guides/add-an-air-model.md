# Add an air model

The air is two parts of the run, each on a ladder from the simplest to the
richest ([decision 0035](../decisions/0035-one-simulator-the-run-every-part-on-a-ladder-of-fidelity.md)),
each model chosen by a scenario's manifest from the registry
(`greenhouse_sim/greenhouse_sim/scenarios/registry.py`,
[decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)):

- **the air field** (`models.air_field`): a prescribed pattern
  (`greenhouse_sim/greenhouse_sim/airflow/prescribed.py`), a steady flow,
  the same at every moment: `uniform`, `buoyancy`, `vortex` or `gradient`;
- **the house's air** (`models.house_air`, P14.6), its days a
  `ClimateDay` (`greenhouse_sim/greenhouse_sim/climate/day.py`):
  - `grid`, the air cell by cell (`ClimateRun`,
    `greenhouse_sim/greenhouse_sim/climate/run.py`) beside the whole
    house: a moment's field from a grid run that starts an hour before the
    moment's hour, or at the run's start in its first two hours;
  - `whole_house`, the whole house alone (`WholeHouseDay`): one well-mixed
    volume, which every moment's field draws the same in every cell, with
    no grid run.

  Either way, the whole house (`WholeHouse`,
  `greenhouse_sim/greenhouse_sim/climate/house.py`), worked exactly over
  stretches of at most a minute, cut at each command, is what the crop and
  the controller's loops read, and what the sensors sample: from the start
  alone, and after the run's first two hours beside the grid.

**CFD** (`greenhouse_sim/greenhouse_sim/cfd/`) is a steady solution kept
from OpenFOAM ([decision 0027](../decisions/0027-cfd-runs-out-of-process-on-the-fields-grid.md)),
a field the viewer asks for beside the others, not a model a manifest
chooses.

A model of either part has a name, unique within its part, a parameter
model told apart by its `kind`, the model's name, and a version, which
goes up whenever its numbers change for the same parameters.

## A prescribed pattern

Its contract is `AirflowModel`
(`greenhouse_sim/greenhouse_sim/airflow/contract.py`): its `field(field_id,
grid, time_s)` gives an environment field with at least its velocity.

1. **The model**, in `greenhouse_sim/greenhouse_sim/airflow/prescribed.py`
   or a module beside it: a frozen pydantic model (`extra="forbid"`) with
   a `kind` literal, its parameters named with their units, and a `field()`
   that gives the velocity and the temperature, its source
   `prescribed:<kind>`.
2. **Its place** in the `PrescribedAirflow` union, and its registry entry,
   a `Model` of `Part.AIR_FIELD` under its kind, with the configuration's
   field that holds it (`airflow`), so that a scenario's manifest can
   choose it in its models
   (`"models": {"air_field": {"model": "<kind>", "parameters": {…}}}`); and
   in `PATTERNS` only if every scenario should offer it.
3. **Nothing else registers it:** `_models` in
   `greenhouse_sim/greenhouse_sim/services/fields.py` offers a scenario's
   own airflow first, then the patterns, CFD, the climate and the shear;
   the API's `/fields` lists them, and the viewer's field list
   (`greenhouse_sim/web/src/fields/FieldControls.tsx`) reads that.
4. **Its tests,** in `greenhouse_sim/tests/test_airflow.py`: beside the
   other models, the flow's shape (no flow through the walls, none made
   from nothing), and the lists of fields that
   `greenhouse_sim/tests/test_fields.py`, `greenhouse_sim/tests/test_climate_field.py`
   and `greenhouse_sim/web/e2e/fields.spec.ts` expect.
5. **Its sources:** each equation and parameter from a cited source, with
   its units and range, or labelled as a heuristic (AGENTS.md, section 5).

## A model of the house's air

The whole house alone was added this way, beside the grid (P14.6).

1. **Its parameters,** a model in `greenhouse_sim/greenhouse_sim/climate/settings.py`
   with its `kind: Literal["<name>"]`, built on `HouseSettings` (the start,
   the glazing, the infiltration) or `ClimateSettings` (which adds the
   grid's mixing), and a `run_settings()` that gives the climate run the
   `ClimateSettings` it works its air out from, as `GridAir` and
   `WholeHouseAir` do.
2. **Its days,** a subclass of `ClimateDay`, overriding what it draws, as
   `WholeHouseDay` does: the field at a moment (`drawn`, `field`), what the
   sensors sample (`sampled`), and the glazing and the openings against its
   air (`glazing_at`, `openings_at`); entered in `DAYS` under its name, by
   which `greenhouse_sim/greenhouse_sim/services/climate_runs.py` builds a
   run's days.
3. **Its choice:** its registry entry, a `Model` of `Part.HOUSE_AIR`, with
   the configuration's field that holds it (`climate`) and its version; and
   its place in `ScenarioConfig.climate`'s union
   (`greenhouse_sim/greenhouse_sim/scenarios/config.py`), so that a manifest
   chooses it (`"models": {"house_air": {"model": "<name>", "parameters": {…}}}`).
4. **Its tests,** as `greenhouse_sim/tests/test_whole_house_air.py` holds the
   whole house: what its house's air is, how its field is drawn, what its
   sensors sample, and what it works out or leaves out. No conformance test
   holds every model of the house's air yet, as
   `greenhouse_sim/tests/test_crop_rungs.py` holds every crop rung: the next
   model is a good moment to write one, in a pull request of its own that
   changes no number.

What the crop and the loops read stays the whole house's. A model whose
air the crop should read otherwise, by zone or by cell, changes what the
crop is given, which [decision 0062](../decisions/0062-a-crop-model-declares-its-scope-drivers-outputs-and-capabilities.md)
gives the crop through named, versioned driver profiles.

## Generated files

```bash
uv run python greenhouse_sim/tests/test_published_schemas.py --update     # a new model in the manifests' schema
```

A change to the reference greenhouse's air moves its replay and its opening
day (`greenhouse_sim/tests/test_replay.py`, `greenhouse_sim/tests/test_opening_day.py`,
each with `--update`).

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_airflow.py greenhouse_sim/tests/test_fields.py \
  greenhouse_sim/tests/test_climate_field.py greenhouse_sim/tests/test_whole_house.py \
  greenhouse_sim/tests/test_whole_house_air.py greenhouse_sim/tests/test_climate_day.py \
  greenhouse_sim/tests/test_model_registry.py greenhouse_sim/tests/test_subpackage_imports.py
uv run check --fast
uv run browser-tests e2e/fields.spec.ts
```

## What else to know

- **A model's version** (`version` in its registry entry) goes up by one
  whenever its numbers change for the same parameters: a run's identity
  covers it (P14.2), so its runs become other runs and a checkpoint made
  with the version before is refused.
- **A field that changes with time is not followed everywhere:** the cells
  read the base flow once, at the start, made to conserve mass
  (`greenhouse_sim/greenhouse_sim/climate/projection.py`), and the viewer
  asks for a moment only for the climate's field.
- **Layers:** `airflow` never imports `scenarios`, which imports it;
  `greenhouse_sim/tests/test_subpackage_imports.py` fails on a new pair
  that import each other.
- **Equivalent calculations only** when a model moves onto a contract: the
  replay digests, the opening day and the golden files stay as they are,
  with no `--update` in that change.
- **The reference greenhouse:** a change to its air changes its run, so its
  opening day, replay and views are written again
  ([add a weather](add-a-weather.md) lists the commands).
