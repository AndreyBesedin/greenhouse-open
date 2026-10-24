# Add a weather

The weather outside a greenhouse is the first part of a run. A run reads it
on its own clock through a `WeatherSource`
(`greenhouse_sim/greenhouse_sim/weather/sources.py`), whatever the kind:

- **a preset**, a synthetic day repeated, which any scenario can be shown
  under with `&weather=<name>` (commit `69e349b`);
- **a recorded file**, measurements read from a CSV, which any scenario can
  also be shown under (commit `b10d649`);
- **a kind of its own**, such as the seasonal weather, which only a
  manifest can choose (commit `74f9121`).

## A preset

1. A `Final` `SyntheticWeather(...)` in
   `greenhouse_sim/greenhouse_sim/weather/presets.py`, every number a
   keyword argument, and its name in `PRESETS`: snake case, not `default`,
   and without `@` or `~`, which mark a cloud cover and a wind's bearing
   (`&weather=cold_spring_day@80~270`).
2. The list of weathers in `greenhouse_sim/tests/test_api.py`: the
   scenario's own, then the presets in order, then the recorded files by
   name.
3. A test of its day in `greenhouse_sim/tests/test_synthetic_weather.py`.

## A recorded file

1. The file, `greenhouse_sim/greenhouse_sim/weather/recorded/<name>.csv`:
   a `timestamp` column, ISO 8601 with its time zone and increasing, and
   `outside_<quantity>` columns, of which the air's temperature and
   relative humidity are required (`RANGES` and `DEFAULTS` in
   `greenhouse_sim/greenhouse_sim/weather/recorded.py`). Gaps up to an hour
   are interpolated.
2. What it is and where its data comes from, in
   `greenhouse_sim/greenhouse_sim/weather/recorded/README.md`.
3. The list of weathers in `greenhouse_sim/tests/test_api.py`, and a test
   that reads it in `greenhouse_sim/tests/test_recorded_weather.py`.

## A kind of its own

1. A module in `greenhouse_sim/greenhouse_sim/weather/`: a frozen model
   (`extra="forbid"`) with a `kind` literal and a `source(site, seed,
   start)` that returns a `WeatherSource`, every draw from the seed.
2. Its place in the union of `ScenarioConfig.weather`
   (`greenhouse_sim/greenhouse_sim/scenarios/config.py`), and its
   registration among the weather's models in
   `greenhouse_sim/greenhouse_sim/scenarios/registry.py`, under its kind,
   so that a manifest can choose it in its models:
   `"models": {"weather": {"model": "<kind>", "parameters": {…}}}`
   ([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)).
3. Its own tests, as `greenhouse_sim/tests/test_seasonal_weather.py` has
   for the seasonal kind: the same seed gives the same weather, and its
   numbers lie where its sources say they should.
4. A source for each of its numbers, in its docstrings (AGENTS.md,
   section 5).

## Generated files

A kind of its own changes the manifests' schema:

```bash
uv run python greenhouse_sim/tests/test_published_schemas.py --update   # scenario.schema.json
```

A change to the reference greenhouse's weather changes its run, and so its
opening day, its replay and its views: `greenhouse_sim/tests/test_opening_day.py`,
`greenhouse_sim/tests/test_replay.py` and `greenhouse_sim/tests/test_reference_qa.py`,
each with `--update`, and the screenshots from CI.

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_weather.py greenhouse_sim/tests/test_synthetic_weather.py \
  greenhouse_sim/tests/test_recorded_weather.py greenhouse_sim/tests/test_seasonal_weather.py \
  greenhouse_sim/tests/test_weather_station.py greenhouse_sim/tests/test_api.py
uv run browser-tests e2e/weather.spec.ts
```

## What else to know

- **The viewer** lists every weather the API names
  (`greenhouse_sim/web/src/weather/WeatherPanel.tsx`), so it needs no
  change for a preset or a file.
- **A preset hides a recorded file** of the same name.
- **A recorded file is as long as its data:** a run longer than the file is
  refused, and every scenario can be shown under every weather, so a day's
  file under a season's run fails after its day.
- **A file's content is its identity:** editing a CSV makes the runs under
  it other runs.
- **Kept data:** `greenhouse_sim/greenhouse_sim/weather/recorded/` is kept
  data for the risk gate, and a file over 2 MB is refused at commit.
