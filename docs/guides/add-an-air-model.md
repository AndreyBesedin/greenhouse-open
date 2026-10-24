# Add an air model

The house's air is one part of the run, on a ladder from the simplest to the
richest ([decision 0035](../decisions/0035-one-simulator-the-run-every-part-on-a-ladder-of-fidelity.md)):

- **prescribed patterns** (`greenhouse_sim/greenhouse_sim/airflow/prescribed.py`):
  a steady flow, the same at every moment;
- **one well-mixed volume** (`WholeHouse`, `greenhouse_sim/greenhouse_sim/climate/house.py`):
  worked exactly over stretches of at most a minute, cut at each command;
  the crop, the thermostat and the sensors read it;
- **the air cell by cell** (`ClimateRun`, `greenhouse_sim/greenhouse_sim/climate/run.py`):
  a moment's field from a grid run that starts an hour before the moment's
  hour, or at the run's start in its first two hours
  (`greenhouse_sim/greenhouse_sim/climate/day.py`);
- **CFD** (`greenhouse_sim/greenhouse_sim/cfd/`): a steady solution kept
  from OpenFOAM ([decision 0027](../decisions/0027-cfd-runs-out-of-process-on-the-fields-grid.md)).

Only the patterns' rung has a contract today, `AirflowModel`
(`greenhouse_sim/greenhouse_sim/airflow/contract.py`): its `field(field_id,
grid, time_s)` gives an environment field with at least its velocity. The
well-mixed volume and the cells are classes the run builds itself
(`AUDIT.1` in the [repository audit](../audits/2026-10-13-repository-audit.md)).
So a pattern is a recipe, and a rung between the volume and the cells is a
contract to write first.

## A prescribed pattern

1. **The model**, in `greenhouse_sim/greenhouse_sim/airflow/prescribed.py`
   or a module beside it: a frozen pydantic model (`extra="forbid"`) with
   a `kind` literal, its parameters named with their units, and a `field()`
   that gives the velocity and the temperature, its source
   `prescribed:<kind>`.
2. **Its place** in the `PrescribedAirflow` union, and its registration
   among the air field's models in
   `greenhouse_sim/greenhouse_sim/scenarios/registry.py`, under its kind, so
   that a scenario's manifest can choose it in its models
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

## A rung of the house's air

A model between the well-mixed volume and the cells (zones, say) starts
with the contract the run calls: what it reads of `WholeHouse` today
(`air_at`, `mean_between`, `heated_j`, `heater_level_at`, `seed`,
`carry_on_from`), as a `typing.Protocol` in a `contract.py` under
`greenhouse_sim/greenhouse_sim/climate/`, with a conformance test run over
every implementation, as `greenhouse_sim/tests/test_model_contracts.py`
does for the engine's. Then `ClimateDay` takes the contract instead of
building `WholeHouse` itself, in a pull request of its own that changes no
number. How a scenario names its rung is not decided yet: the first such
model writes that decision.

## Generated files

```bash
uv run python greenhouse_sim/tests/test_published_schemas.py --update     # a new kind in the manifests' schema
uv run python greenhouse_sim/tests/test_reference_baseline.py --update    # a scenario whose air changed
```

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_airflow.py greenhouse_sim/tests/test_fields.py \
  greenhouse_sim/tests/test_climate_field.py greenhouse_sim/tests/test_whole_house.py \
  greenhouse_sim/tests/test_climate_day.py greenhouse_sim/tests/test_subpackage_imports.py
uv run check --fast
uv run browser-tests e2e/fields.spec.ts
```

## What else to know

- **A field that changes with time is not followed everywhere:** the cells
  read the base flow once, at the start, made to conserve mass
  (`greenhouse_sim/greenhouse_sim/climate/projection.py`), and the viewer
  asks for a moment only for the climate's field.
- **Layers:** `airflow` never imports `scenarios`, which imports it;
  `greenhouse_sim/tests/test_subpackage_imports.py` fails on a new pair
  that import each other.
- **Equivalent calculations only** when the run moves onto a contract: the
  replay digests, the opening day and the golden files stay as they are,
  with no `--update` in that change.
- **The reference greenhouse:** a change to its air changes its run, so its
  opening day, replay and views are written again
  ([add a weather](add-a-weather.md) lists the commands).
