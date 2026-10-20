# Add a layout

A layout places a scenario's fixtures, equipment, sensors and planting
positions inside its greenhouse. A scenario's first layout is
`default.json`; any other is another file in the same folder, which the API
serves with `?layout=<name>` and the viewer offers in the scenarios table.
The tomato compartment's `propagation` layout is one (commit `7bc75c0`).

## Steps

1. **The file:** `greenhouse_sim/greenhouse_sim/scenarios/layouts/<scenario>/<name>.json`.
   Its name is lower case letters, digits and `_` (`LAYOUT_NAME` in
   `greenhouse_sim/greenhouse_sim/scenarios/layout_files.py`); nothing else
   registers it. Start from `default.json`: a layout file holds exactly
   what `layout_document` writes, its defaults included.
2. **It fits its scenario:** everything inside the greenhouse but a weather
   station's instruments, at least as many planting positions as the crop
   has plants, and every piece of equipment that the manifest's daily
   commands and thermostat name.
3. **Its identifiers** hold only letters, digits, `_`, `.` and `-`, since
   the API's parameters carry them.
4. **Name it in the tests that list layouts:** `OTHER_LAYOUTS` in
   `greenhouse_sim/tests/test_api.py`, and, for the tomato compartment,
   `greenhouse_sim/tests/test_services.py`.
5. **Test what it is for,** beside the others in
   `greenhouse_sim/tests/test_layout_files.py`: the propagation layout's
   test checks that it carries the same rows, on benches.

The viewer needs nothing: a scenario with more than one layout gets a picker,
and the address keeps the choice (`&layout=<name>`).

## Generated files

None, unless the layout's model changes, which
`uv run python greenhouse_sim/tests/test_published_schemas.py --update`
publishes. A scenario solved by CFD keeps a solution for each layout
(`greenhouse_sim/greenhouse_sim/cfd/results/`), which CI's CFD workflow
(`.github/workflows/cfd.yml`) solves, with OpenFOAM, a line for each
([decision 0027](../decisions/0027-cfd-runs-out-of-process-on-the-fields-grid.md)).

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_layout_files.py greenhouse_sim/tests/test_api.py \
  greenhouse_sim/tests/test_services.py
uv run browser-tests e2e/layouts.spec.ts
```

## What else to know

- A name the glob finds but `load_layout` refuses (capitals, a hyphen)
  fails the tests that run over every layout.
- In an address, `~` after a layout's name starts the moves made to it
  (`default~heater:1:0`), so a name never holds one.
- A new file changes no run, no digest and no baseline. A change to a
  `default.json` does, as to any part of a scenario.
