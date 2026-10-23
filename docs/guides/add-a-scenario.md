# Add a scenario

A scenario is a versioned JSON manifest, with a layout file beside it
([decision 0031](../decisions/0031-scenarios-are-versioned-json-manifests.md)).
The simulator finds both by their file names, the API lists the scenario, and
the viewer opens it with `?scenario=<id>`. Nothing registers it by hand.
The reference greenhouse was added this way (commit `ca527ae`).

## Steps

1. **Its layout:** `greenhouse_sim/greenhouse_sim/scenarios/layouts/<id>/default.json`,
   started from a sibling's, with `"$schema": "../../layout.schema.json"`.
   Its crop rows are the scenario's plants: so many rows of so many
   planting positions. See [add a layout](add-a-layout.md) for what a
   layout file must be.
2. **Its manifest:** `greenhouse_sim/greenhouse_sim/scenarios/manifests/<id>.json`,
   with `"$schema": "../scenario.schema.json"`, `"schema_version": 4`, a
   `greenhouse_id` equal to its file's name, and its house as an
   `installation` ([decision 0050](../decisions/0050-an-installation-is-the-house-part-of-a-scenario.md)):
   an `installation_id`, a `name`, its `envelope`, `"layout": "default"`
   and a crop for every row, `row_crops`, each with its `row`,
   `crop_model` and `variety`, the same for all rows. The schema (`greenhouse_sim/greenhouse_sim/scenarios/scenario.schema.json`)
   names the fields it must have and refuses any it does not know, at any
   depth. Its `random_seed` is its own, apart from every other scenario's.
   Its `notes` explain its numbers, by field.
3. **The tests that list every scenario** name it too:
   - `greenhouse_sim/tests/test_scenarios.py`: the registry, the reference
     scenario first and the others by identifier;
   - `greenhouse_sim/tests/test_airflow.py`: the airflow it names;
   - `greenhouse_sim/tests/test_weather.py`: its weather, unless it is the
     constant one;
   - `greenhouse_sim/tests/test_opening_day.py`: the scenarios without an
     opening day;
   - `greenhouse_sim/tests/test_api.py`: its other layouts, if it has some.
4. **Its baseline:** the reference baseline records every scenario's first
   week, so it is written again (below).
5. **The viewer** needs nothing: its scenario list reads the API's. A
   browser test of what is special about it, as
   `greenhouse_sim/web/e2e/reference-greenhouse.spec.ts` is for the
   reference greenhouse, is worth writing.

## Generated files

```bash
uv run python greenhouse_sim/tests/test_reference_baseline.py --update
```

An **opening day** (`opening_day` in the manifest) needs its kept day, and
its kept day with everything off, in `greenhouse_sim/greenhouse_sim/scenarios/openings/`.
`greenhouse_sim/tests/test_opening_day.py --update` writes them, for the
reference greenhouse only today, in about six minutes: another scenario's
needs that test extended.

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_scenarios.py greenhouse_sim/tests/test_scenario_manifests.py \
  greenhouse_sim/tests/test_layout_files.py greenhouse_sim/tests/test_api.py \
  greenhouse_sim/tests/test_airflow.py greenhouse_sim/tests/test_weather.py \
  greenhouse_sim/tests/test_reference_baseline.py
uv run check --fast
```

## What else to know

- **The checks a scenario meets** without saying so: its site is the
  default one (`greenhouse_sim/tests/test_site.py`), it runs a week at
  least (the baseline inspects its seventh day), and only the reference
  greenhouse has daily commands and the organ-level crop.
- **Any change to a manifest,** a note included, changes its digest, so its
  kept checkpoints are refused until written again, and its runs are other
  runs ([decision 0042](../decisions/0042-a-season-a-thermostat-and-the-heat-it-gives-as-a-modelled-record.md)).
- **Kept data:** the openings and `greenhouse_sim/tests/fixtures/` are kept
  data for the risk gate, so the pull request asks for a manual review.
