# Repository audit, 13 October 2026

**Scope:** the whole repository after P09: the three Python packages, the
browser viewer, the tests, the checks, the CI and the documents.
**Question asked:** what has to change for the repository to take a hundred
contributors, and to let someone add a model, a device or a scenario
without understanding the whole architecture, by hand or through an AI
assistant.
**Verdict:** keep the architecture. Its boundaries are real, named and
enforced, which is rare at this age. What stands between it and that
future is not design but scale: the same request written out twenty times,
caches held in module globals, a plug-in story that the reference scenario
no longer uses, no recipes, and a 21-minute check. The findings below are
numbered `AUDIT.1` to `AUDIT.21`; the [order of work](#order-of-work) at
the end groups them into the pull requests that would follow.

Part of the [audits](README.md). The earlier frontend audits of 6 and 11
October are recorded in the roadmap's
[frontend maintenance plan](../roadmap/frontend-maintenance.md).

## Provenance

- **Commit audited:** `1497c30` on `main` ("Merge pull request #145"),
  2026-10-13, with #141 to #146 merged: P09.9's one command, the demo
  walkthrough, the checkpoint hour, the browser lanes (decision 0032) and
  the Dependabot plan.
- **What was read:** every module docstring of the simulator, the core,
  the model contracts, the climate's house model and sources, the services'
  caches, the API's routes and server, the scenario configuration and the
  reference manifest, the viewer's `App`, scene source and loaders, every
  guardrail test and check script, the CI workflows, the risk gate, and
  the engineering, contributing and roadmap documents.
- **What was measured:** sizes, the import graph between subpackages,
  function lengths and parameter counts, what stricter Ruff rule sets would
  flag, repeated helper names, the viewer's state and loaders, docstring
  coverage and sentence length, and the simulator's test suite with
  per-test timings.
- **Run:** the simulator's full test suite with `--durations`, locally
  (3,532 passed, 4 skipped, 9 min 20 s); the publishable checks on this
  document.
- **Not run:** the browser tests, the visual comparison, the CFD tests and
  the benchmark; their CI results on #144 and #146 were read instead.

## The repository in numbers

| | Lines | Files | Tests |
| --- | --- | --- | --- |
| `greenhouse_protocol` | 1,766 | 22 | 47 |
| `greenhouse_sim` (package) | 19,502 | 153 | 845 in 99 files, 17,008 lines |
| `greenhouse_adapters` | 3,430 | 39 | 52 |
| viewer source (hand-written) | 15,424 | 273 with tests | 387 unit, 118 browser in 50 specs |
| documents | 9,338 | 32 decisions, 13 roadmap documents | |

577 commits by one author since 2026-09-24. The last 150 commits touch a
median of 1 file and, at the 90th percentile, 13. The most changed files
are `web/src/App.tsx` and `web/README.md` (52 commits each),
`api/routes.py` (36), `web/src/styles.css` (34) and `services/fields.py`
(32): the hubs this audit comes back to.

## Assessment

What to keep, because it works:

- **Named boundaries, each with a test.** The protocol depends on nothing;
  a package imports only what it declares (`tests/test_dependencies.py`);
  the domain depends on nothing else and holds every shared kind
  (`test_domain.py`); only the plant model reads its own state
  (`test_model_state_boundary.py`); ground truth is read by evaluation only;
  APIs reach their package through services only (`check_api_layers.py`);
  the public import paths are listed (`test_public_imports.py`).
- **Contracts generated, not copied.** The scene, the field and the CFD
  geometry are Pydantic models whose JSON Schemas are committed and turned
  into the viewer's types and validators, and tests fail when either side
  drifts. The scenario manifests and layouts are checked against schemas
  generated the same way.
- **Numbers carry names,** enforced on both sides (`check_named_constants.py`,
  Biome's `noMagicNumbers`). Strict mypy and strict TypeScript, with no
  `type: ignore`, no `noqa`, no `Any` in the packages, two `as unknown as`
  in the viewer, nine explained `biome-ignore`s and no TODO anywhere.
- **Decisions and roadmap in the repository,** 32 records, each superseded
  rather than edited, and a roadmap that records what was built against
  what was planned.
- **Models plug in through protocols** (decision 0006): `PlantModel`,
  `EnvironmentModel`, `SensorModel`, `AirflowModel`, `WeatherSource`,
  `Environment`, `CropLight`, `WorldCheckpoints`, `ActionExecutor`, each
  with a reference implementation and a contract test.
- **Determinism by construction:** every draw seeded from the scenario's
  seed, the process, the subject and the index; characterization and golden
  tests hold the numbers.

Where it will not scale as it stands: the sections below.

## Findings

### A. Modularity: adding a model, a device or a scenario

#### AUDIT.1: Two simulation paths, and the contracts belong to the older one

The simulator has two ways of running a scenario:

- **The engine's day,** `core/engine.py`: `SimulationEngine` advances a
  `GreenhouseWorld` a day at a time through `EnvironmentModel`,
  `PlantModel` and `SensorModel`, with the simple tomato model, the simple
  environment and the simple sensor model. This is what `greenhouse_sim.engine`
  exports, what the examples run, what the live stream plays, and what the
  README's "Write or compose a model" row points at.
- **The run,** built from P05 to P09: the house's air every minute
  (`climate/`), the sun (`solar/`), the organ-level crop living each day in
  that air and light (`core/crop.py`), sensors sampling that run
  (`sensors/air.py`, `sensors/log.py`), checkpoints, branches and replay.
  This is what the reference scenario is, what the viewer draws, and what
  every service from `fields` to `run_state` serves.

The run path has its own protocols (`CropLight`, `Environment`,
`WeatherSource`, `AirflowModel`) but none for the air model: the
well-mixed house is a class, `WholeHouse`, that the services instantiate
directly; the grid run, `ClimateRun`, likewise. The three contracts the
README advertises for model writers are the engine's, and the reference
scenario does not pass through them. The P09 document records this as a
known approximation ("the live run grows the simple model") and a review
decision (the organ crop in the reference scenario only).

Someone arriving to "add an air-flow model" or "add a plant model" finds a
contract that the flagship scenario does not use, and a flagship path with
no contract. For the low-code goal this is the first thing to settle.

Acceptance:

- One decision record says which path is the simulator and what becomes of
  the other: either the engine's models are re-homed as rungs of the run
  (the simple daily model as a `CropModel` beside `organ`, the simple
  environment as the lowest rung of the air), or the engine is kept for
  batch runs and said to be so.
- The run's exchangeable parts have contracts in `contract.py` files, as
  the engine's do: the house's air (`HouseAirModel`: `advance(air, steady,
  outside, duration)`), the cell-by-cell air, the plant's day, the sensor's
  sample. Each contract has a conformance test parametrized over its
  implementations, as `test_model_contracts.py` is.
- The README's public API table points at the contracts a contributor
  would implement today.

#### AUDIT.2: Models are chosen by code, not by the manifest

A manifest chooses its weather (`kind: constant | synthetic | recorded`)
and its airflow (`kind: uniform | ...`) by a discriminator, and the schema
lists the kinds: that is the right shape. But the crop model is a closed
enum (`CropModel.SIMPLE | ORGAN`), the house's air has no choice, the
sensor model none, the plant's responses none, and nothing outside the
package can add a kind. The engine takes models by constructor injection,
which only Python code can do. There is no registry of model kinds and no
entry point by which an installed package could register one.

Acceptance:

- Every exchangeable model is a `kind`-discriminated section of the
  manifest: `air`, `crop`, `sensors`, `light`, with the model's own
  parameters inside its section. The manifest's schema version moves
  (decision 0031 provides for it) and the six manifests are rewritten by a
  script, with the existing field-by-field test holding their meaning.
- A registry per contract maps a kind to its model class, filled from the
  package's own kinds and from `importlib.metadata` entry points (a group
  per contract, such as `greenhouse_sim.air_models`), so that
  `pip install greenhouse-air-cfd` adds a kind without a change here. The
  schema exported for the viewer lists the kinds registered.
- A contributed model is a folder with the model, its parameters, its
  contract test and one manifest that uses it, and nothing else changes.
  The guide in AUDIT.5 shows this end to end.

#### AUDIT.3: A new device touches ten files

Adding a fourth piece of equipment (a CO₂ doser, a fogging line, a
screen) today means: a member of `domain.equipment.ActuatorKind`; a class
in `world/equipment.py`; an `isinstance` branch in `climate/sources.py`;
a member of `scene.snapshot.SceneEntityKind`; its entity in
`scene/snapshot.py`; its renderer in the viewer's `RENDERERS`, a category
in `debug/categories.ts`, its controls; and, where it changes the house,
`climate/house.py` and `climate/settings.py`. Sensors follow the same
shape. This is the one place where the "no generic layer until a second
implementation" rule has three implementations and still no layer.

Acceptance:

- A device says what it does to the air through one protocol, as
  `sources.py` already describes in prose: its velocity added, heat added
  and water removed per cell at a level, and what it obstructs. `sources.py`
  dispatches on the protocol, not on the class.
- The scene publishes one `EQUIPMENT` kind (and one `SENSOR`, as it does)
  with the device's kind as an attribute, so the viewer draws an unknown
  device as its box in its colour, and a renderer is an improvement, not a
  compile error. The typed renderer registry keeps its guarantee for the
  kinds that have one.
- The layout schema's `equipment` items take their kinds from the device
  registry (AUDIT.2), so a layout can place a contributed device.
- A test lists how many files mention each device kind, as the domain test
  lists enums, and fails when a kind is named outside its owner and the
  registry.

#### AUDIT.4: One model's parameters sit at the top of every scenario

`ScenarioConfig` carries about 25 flat fields that belong to the simple
daily model and its sensor noise (`water_capacity_ml`,
`stem_growth_cm_per_day_base`, `truss_interval_days`,
`fruit_count_noise_probability`, ...), beside the nested sections the later
projects added (`climate`, `weather`, `airflow`, `cfd`, `site`,
`crop_work`). The reference scenario, which does not use that model,
carries them anyway, and a reader of its manifest cannot tell which numbers
act on its run.

Acceptance: those fields move into the simple model's section under
`crop` (AUDIT.2) and the sensor model's under `sensors`, with the
manifests rewritten and the schema version moved. `ScenarioConfig` then
reads as the world and its chosen models, each with its own numbers.

#### AUDIT.5: There is no recipe, for a person or an assistant

The documents explain the direction (roadmap, 999 lines for P09), the
rules (engineering) and the decisions. None of them answers "how do I add
a scenario, a layout, a weather day, a device, a model?" in the order a
contributor would do it, ending in the test that proves it. The viewer's
README explains its scenes and checks but not how a panel or a loader is
added. `.github/copilot-instructions.md` holds the invariants for one
reviewer; no `AGENTS.md` or `CLAUDE.md` at the root offers them to any
other assistant, nor the commands to check a change.

Acceptance:

- A `guides` folder beside the decisions, one short recipe each, with the
  files touched and the test to run: a scenario from a manifest; a layout; a weather; a device;
  an air model; a plant model; a viewer panel with its loader; an API route
  with its service. Each recipe is checked by a test that the files it
  names exist, as the citation test checks documents.
- A root `AGENTS.md` (and `CLAUDE.md` pointing at it) that says where the
  rules are, what to run before a commit, where the guides are and which
  files are generated. The Copilot instructions become one reader of it.

### B. Repeated patterns, and the toolboxes they want

#### AUDIT.6: The run request is written out 22 times

A run is asked for by eight things: the scenario, its layout, its
equipment's levels, its openings, its commands, its daily commands, its
weather and the moment. The API reads them from the query in fourteen
`match` arms of `respond` (226 lines), each calling `_pairs`, `_commands`,
`_daily`, `_seconds`, `_last` in turn; 22 service functions take them as
eight positional parameters (`fields.field`, `house_air`, `glazing`,
`openings`, `climate_probes`, `crop.run_crop`, `crop_scene`, `crop_plant`,
`plants_light`, `sensors.observations`, `sensors_at`, `truth`,
`run_state`, `timeline`, `save_checkpoint`, `replay.day_probes`, ...); 37
functions in the packages take six or more parameters, nearly all these.
The checkpoint's model, `Checkpoint`, already names the same eight fields.
The viewer already has the value object the Python side lacks:
`ScenarioRun` with `runParameters(run, parts)`.

Acceptance:

- A frozen `RunRequest` in `services/runs.py` (scenario, layout, levels,
  openings, commands, daily, weather, moment), parsed once by the API
  (`_run_request(scenario_id, query)`) and taken by every service that
  takes a run; `Checkpoint` carries one. `_checked` and `run_schedule`
  become its methods or take it.
- Ruff's `PLR0913` at six parameters then holds, and `respond` shrinks to
  one line per route.

#### AUDIT.7: Four caches, four locks, three `forget_` functions

`services/fields.py` (`_KEPT`, 8 climate runs), `services/crop.py`
(`_KEPT`, 4 crops), `services/checkpoints.py` (`_KEPT`, 16 checkpoints)
and `services/kept_states.py` (`_STATES`) each hold a module-level
`OrderedDict` behind a module-level lock, with its own bounded-eviction
loop and a `forget_*` for tests. `test_benchmark.py`'s fixture forgets
them all, which drops the opening-day checkpoints the API loaded at start,
so every test after it works its days out from the start: the repository
checks went from 10.2 to 20.6 minutes at #140. The flaky checkpoint tests
found while pushing #144 (kept moments in `house._kept`, a refusal
answered 200) are the same order dependence seen from the other side.

Acceptance:

- One `Kept[K, V]` in `services/kept.py`: bounded, locked, `get`, `keep`,
  `forget`; the four caches are instances of it. One
  `services.caches.forget_everything()` for tests, and a fixture in the
  simulator's `conftest.py` that forgets and reloads the openings around
  any test that asks for a clean slate, so no test can leave the suite
  slower than it found it.
- Longer term (AUDIT.15), the caches live on a simulator object the server
  and the tests create, not in modules.

#### AUDIT.8: The viewer validates by hand what the simulator could publish

Three API responses arrive as generated contracts; the other fifteen or
so (`loadHouseAir`, `loadWeather`, `loadWeatherDay`, `loadProbeCharts`,
`loadRunState`, `loadRunManifest`, `loadTimeline`, `loadSensorReadings`,
`loadCropPlant`, `loadPlantsLight`, `loadCheckpoints`, `loadScenarios`,
...) are parsed by hand with `isObject` (written five times) and
`isNumbers` (four times, with two different meanings), each in a
`try { fetch; ok; json; parse } catch` of the same ten lines. Each of those
responses is already a Pydantic model on the Python side (`HouseTrace`,
`RunState`, `RunManifest`, `SensorObservations`, `Checkpoint`, ...). The
chart components repeat `WIDTH`, `HEIGHT` and `PERCENT` seven times,
`POINT_DECIMALS` four times and `polyline` three times.

Acceptance:

- The simulator publishes one schema per service result that the viewer
  reads, from a single list of published contracts
  (`scene/contracts.py`, say) that `generateContractSources.ts` consumes;
  the generated-files test covers them all. The hand parsers go.
- One `loadJson(url, validate, fetchFn)` in `useLoad.ts` or beside it
  replaces the fifteen loaders' bodies; a loader is then the URL builder
  and the validator.
- `charts/` holds the SVG chart primitives (`polyline`, axes, the frame's
  sizes) that the probe, house-air, weather and plant-day charts share.

#### AUDIT.9: Small Python toolboxes worth naming

- **"The latest kept before a moment"** is written with `bisect` in
  `climate/house.py`, `climate/openings.py`, `weather/recorded.py` and
  `weather/sources.py`: one `core/moments.py` with a `Kept` series type
  (`insort`, `latest_before`, `between`).
- **Short digests** name a manifest (8 hex digits), a climate run (8), a
  checkpoint (16), a replay (`DIGEST_LENGTH`) and a CFD result, each with
  its own `hashlib.sha256(...).hexdigest()[:N]`: one
  `core/digests.short_digest(text, length)`, and one place to change the
  algorithm.
- **Schema export and "the committed file equals the export"** is written
  for the scene, the field, the CFD geometry, the manifest and the layout:
  one `contracts.publish(model, path)` and one parametrized test.
- `_between` is defined in two modules; `_within`, `_vector`, `_unit`,
  `_rounded`, `_pairs`, `_checked` and `_every` are defined twice each
  with different meanings, which a reader has to check each time. Rename
  towards what each does, or share the ones that are the same.

### C. Rules and guardrails missing

#### AUDIT.10: The layering between subpackages is not checked

The domain is kept at the bottom and the API at the top, and nothing in
between is checked. The import graph has ten mutually importing pairs:
`core`↔`biology`, `core`↔`climate`, `core`↔`scenarios`, `core`↔`sensors`,
`core`↔`environment`, `biology`↔`world`, `climate`↔`weather`,
`solar`↔`weather`, `cfd`↔`scenarios` and `cfd`↔`services`
(`cfd/__main__.py` imports the services). `core` imports `climate`,
`solar`, `scenarios`, `sensors` and `environment`: it is not the core of
anything, it is the engine and the run's crop, which sit above the
models.

Acceptance:

- A decision names the layers: `domain` < `world`, `fields` <
  `weather`, `solar`, `airflow`, `biology` < `climate`, `sensors`,
  `cfd` < `scenarios` < `core` (or renamed `run`) < `scene`, `evaluation` <
  `services` < `api`, with the cycles broken (a `weather` that needs the
  sun's position imports `solar`, not the reverse; `cfd/__main__` moves to
  `scripts/` or calls its own package).
- A test holds the table, as `test_domain.py` does for one layer, or
  `import-linter` with the same table in `pyproject.toml`.

#### AUDIT.11: Ruff checks five rule families

`select = ["E", "F", "I", "UP", "B"]`. A dry run of other families over the
three packages: `PLR0913` too many arguments 37 (AUDIT.6), `C901` 5,
`RUF` 41, `ARG` unused arguments 14, `N` naming 11, `SIM` 2, `PERF` 1,
`ERA` commented-out code 2, `D1` missing public docstrings 298 (19% of
public functions and classes have none). `TRY` flags 174, nearly all long
messages built in `raise`, which this codebase does on purpose. The viewer
runs Biome's recommended set, which is broader.

Acceptance: enable `SIM`, `C4`, `RUF`, `ARG`, `PERF`, `PTH`, `N`, `ERA`
and `PLR09` (`max-args = 6`, after AUDIT.6; `max-complexity = 10`) in one
pull request that fixes what they find; `D1` for the packages' public
names once AUDIT.16's docstring shape is agreed. Record the choice in a
decision beside 0010.

#### AUDIT.12: The checks take 21 minutes, in one job, with no cancellation

The repository checks run ruff, mypy and pytest for three packages and the
root, serially, in one job: 20.6 minutes since #140 (10.2 before it, see
AUDIT.7). The browser lanes take 6 to 8. `ci.yml` has no `concurrency`
group, so a stack of pull requests pushed together runs every job of every
push to the end, while `pr-risk.yml` cancels its own. `pytest-xdist` is in
the environment and used by nothing. The simulator's slowest tests are
seasons through the reference scenario, which are integration tests, not
the fast loop.

Measured locally for this audit, the simulator's suite (3,532 tests, 4
skipped) took 9 min 20 s, and two tests took half of it:

| Test | Seconds | Marked `slow` |
| --- | --- | --- |
| `test_opening_day.py::test_replayed_from_the_runs_start_the_opening_day_is_the_one_kept` | 188 | yes, run by CI's full pass all the same |
| `test_replay.py::test_a_replay_gives_the_same_digests_and_a_branch_the_same_before_its_change` | 103 | no |
| `test_reference_qa.py::test_the_kept_views_are_what_the_simulator_gives` | 20 | yes |
| `test_reference_schedule.py::test_the_winds_direction_can_be_overridden_for_qa_and_an_open_door_follows_it` | 14 | no |
| `test_daily_schedules.py::test_the_sensors_read_a_daily_schedules_run` | 12 | no |
| `test_season_runs.py::test_a_days_log_is_the_whole_logs_from_that_day_on` | 11 | no |
| `test_controlled_day.py::test_a_schedule_opens_and_shuts_a_vent` | 10 | no |

The seven together are 64% of the suite; the other 3,525 tests take about
3 min 20 s. The replay test's 103 s may itself be inflated by the
benchmark's fixture having dropped the opening days earlier in the same
run (AUDIT.7); that is not proven here. Only four test files use the
`slow` mark, and `scripts/check.py` runs the slow tests on every pull
request: `--fast` is the pre-push hook's, not CI's.

Acceptance:

- `concurrency: ci-${{ github.ref }}` with `cancel-in-progress` on pull
  requests.
- The repository checks as a matrix (`protocol`, `sim`, `adapters`,
  `root`), with `pip` cached, and the simulator's tests under `-n auto`
  once AUDIT.7 removes the order dependence.
- Season-long tests marked `slow` (the replay test is not) and run
  nightly and on `main`, with `--fast` the pull request's default, as the
  roadmap's CI-time note already proposes. Those two marks alone take
  about five minutes off every pull request's checks.
- The target recorded in that note: a pull request's checks under ten
  minutes end to end.

#### AUDIT.13: Supply-chain and repository hygiene for many contributors

No `permissions:` block in any workflow (the default token can write);
actions pinned to major tags, not digests; no `pip-audit` or `npm audit`
step; no Dependabot yet (planned, roadmap README); no `SECURITY.md`,
`CODEOWNERS` or issue templates; the `main` ruleset requires no status
checks, which the Dependabot plan already notes; one git tag and a
`CHANGELOG.md` whose "Unreleased" has grown for three weeks.

Acceptance: `permissions: contents: read` at the top of each workflow,
digests for the actions (Dependabot keeps them current), an audit step in
the repository checks, `SECURITY.md` and issue templates, `CODEOWNERS`
once there is more than one owner, required checks on `main`, and a first
release (`0.1.0`) with its changelog cut, so that later entries are short.

#### AUDIT.14: Nothing logs

No module in the three packages imports `logging`. The server prints
tracebacks to stderr; the services say nothing about what they computed,
took over from a kept state, or evicted. The flaky tests of AUDIT.7 were
diagnosed by reading code, because there was nothing to read from a run.

Acceptance: a `logging` logger per subpackage with a `NullHandler` at the
package root; the services log at `INFO` when a run is made, taken over
or evicted, with the run's digest; the server configures logging and logs
each request's path, status and time. Tests can then assert on `caplog`
instead of on cache internals.

#### AUDIT.15: Module globals and threads make tests order-dependent

Besides the caches (AUDIT.7), `SCENARIO_REGISTRY` is read at import, the
live runs pace on daemon threads that tests do not join, and the API test's
server runs on a daemon thread. Ten modules import `threading`. A test
that leaves a thread or a cache behind changes what the next test sees,
which is why the same suite passes alone and fails in the pre-push hook.

Acceptance: a `Simulator` object that owns the scenario registry, the
caches and the live runs, created by the server and by a test fixture, so
that two simulators in one process do not see each other; module-level
state limited to constants. This is the enabling step for `-n auto` and
for a server that serves more than one user.

### D. Readability

#### AUDIT.16: The prose is consistent, dense and tied to the roadmap

The documents and docstrings have one voice, and it is a good one for a
reader who stays. Measured over the simulator's module docstrings:
sentences of 20 words at the median, 44 at the 90th percentile, one of
841 words (a bulleted list written as one sentence); 115 roadmap step tags
(`P09.3`, `P07.1`) in 64 source files; and the API documented as a
150-line table in `routes.py`'s docstring, kept by hand beside 32 routes.
81% of public functions and classes have a docstring. A newcomer, or an
assistant with a context window, pays for every word before the first
line of code, and cannot tell a step tag from a type.

Acceptance:

- A docstring shape in `docs/engineering.md`: a first line that says what
  the thing is; then its units, its contract and what it refuses; prose
  about the project's history goes to the roadmap, cited by step. Step
  tags stay in module docstrings and decision records, not in function
  bodies.
- The route table generated from the `match` arms by a test (a `routes.md`
  that fails when stale), or an OpenAPI document once the API has a second
  client.
- Lists written as lists.

#### AUDIT.17: Four hubs carry the weight

`api/routes.py` 669 lines (`respond` 226), `services/fields.py` 630,
`web/src/App.tsx` 676 (18 `useState`s, about 20 `useLoad`s, 17 props to
`ScenarioPanels`), `web/src/scene/source.ts` 630 (a `SceneSource` union
with 20 optional fields and its address codec). The two viewer files are
the most changed in the repository. FE-AUDIT.11 moved the panels out of
`App`; the loads and the state stayed.

Acceptance:

- AUDIT.6 shrinks `routes.py`; `fields.py` splits into the climate run's
  cache and the field, probe, house, glazing and openings services it
  already has sections for.
- `App` keeps the source and the selection; each feature owns a hook that
  takes the run and returns its loads (`useClimateLoads(run)`,
  `useSensorLoads(run, selected)`, `useQaLoads(run, qaMode)`), and its
  panel takes that hook's result as one prop. The viewer's state moves to
  a reducer or a store when the third such hook appears.
- `source.ts` splits the type and its address codec from the helpers that
  edit a source (`levelsAt`, `withOverride`, `withItsAir`), which go to
  `scene/edits.ts` where the others already are.

#### AUDIT.18: The test suite's shape

99 test files in one folder, named by feature; golden files updated three
different ways (`python tests/test_x.py --update`); marks limited to
`slow` and `cfd`; no folder mirrors the subpackages; 17,008 lines of tests
for 19,502 of code, which is healthy. The viewer's 387 unit tests and 118
browser tests are well placed; the browser tests use 26 explicit
`timeout: 20_000` and 6 `waitForTimeout`s, each a place a slow machine
fails.

Acceptance: `tests/<area>/` mirroring the subpackages; one
`--update-golden` option in `conftest.py`; marks for `season`,
`contract`, `golden`; browser waits on state, not time, with one shared
`ARRIVES` timeout as the crop spec now does.

### E. Inefficiencies

#### AUDIT.19: What the benchmark and the CI already point at

P09.8's benchmark notes, not yet acted on: the sun's heat through the
glass is computed every minute (about 70% of the house's air);
`Schedule.applied` scans the whole schedule twice per step. The opening-day
cache dropped by the benchmark test doubles the repository checks
(AUDIT.7). Every change of the viewer's run fires about twelve requests
that each re-validate the same run (`_checked`, `run_schedule`), cheap
because the climate run is cached but repeated for nothing.

Acceptance: the sun's glass heat kept per stretch between weather changes;
`Schedule` indexed by moment (AUDIT.9's `moments`); `RunRequest`
(AUDIT.6) validated once and cached by digest; the benchmark's report
compared in CI as a non-blocking comment, so a regression is seen on the
pull request that makes it.

#### AUDIT.20: The viewer's global stylesheet and bundle

`styles.css` is 963 lines and 162 selectors in one global namespace,
changed by 34 commits; the bundle is about 1.3 MB minified, which the
viewer's role as a local tool justifies today. With many contributors,
class names collide and nobody dares delete a rule.

Acceptance: CSS modules, or one naming convention (`panel-`, `hud-`,
`chart-`) with a Biome or stylelint rule; a coverage-like report of unused
selectors from the browser tests; the bundle budget recorded in
`vite.config.ts` as it is.

### F. Collaboration

#### AUDIT.21: The process is one developer's, and says so

Nineteen stacked pull requests merged with merge commits; a review policy
that requires no human approval; one `main` ruleset without required
checks; a 500-line gate that asks the author to tick a box; a changelog
without a release. All of it documented and deliberate
(`docs/engineering.md`, "Solo-developer review policy"). It will not
survive contact with a second regular contributor, and the document knows
it.

Acceptance, when the second contributor arrives: required checks and one
approval on `main`; `CODEOWNERS` by subpackage with the owner's name in
each subpackage's `__init__` docstring; squash merges for contributed
branches; a label taxonomy (`model`, `device`, `scenario`, `viewer`,
`good first issue`) seeded from this audit's findings; a release every
roadmap project. Until then, the audit's own work is a good test of the
guides (AUDIT.5): each can be done from the recipe alone.

## Order of work

Each step is one pull request or a short stack, and each leaves the
repository runnable.

1. **Stop the bleeding in CI** (AUDIT.7, AUDIT.12): `Kept`,
   `forget_everything`, the openings reloaded around the benchmark test,
   `concurrency` on `ci.yml`, the checks as a matrix. Expected: the
   repository checks back near ten minutes, the flaky tests gone.
2. **The run request** (AUDIT.6): `RunRequest`, parsed once, taken by
   every service and by `Checkpoint`. Mechanical, large, and the
   precondition for the rules of step 5.
3. **The contracts the viewer reads** (AUDIT.8, AUDIT.9): every service
   result published as a schema, one loader, one chart toolbox, one digest
   and one moments module.
4. **Layers and the simulator object** (AUDIT.10, AUDIT.15, AUDIT.14): the
   layer table and its test, the cycles broken, `Simulator` owning the
   caches and the registry, logging. `-n auto` follows.
5. **Rules** (AUDIT.11, AUDIT.13): the Ruff families, `permissions`,
   digests, audit steps, `SECURITY.md`, templates, the first release.
6. **Models as manifest sections with registries** (AUDIT.1, AUDIT.2,
   AUDIT.3, AUDIT.4): the decision on the two paths, contracts for the
   run's parts, `kind` sections with entry points, devices by capability,
   the simple model's numbers in its section. This is the roadmap project
   that makes the low-code goal real, and the one to plan first.
7. **Guides and the assistant's entry point** (AUDIT.5, AUDIT.16): the
   recipes, `AGENTS.md`, the docstring shape, the generated route table.
   Written last so that they describe what steps 1 to 6 leave.
8. **The hubs** (AUDIT.17, AUDIT.18, AUDIT.19, AUDIT.20) as the files are
   touched, each in its own pull request.

Steps 1 and 2 need no roadmap decision and can start now. Step 6 is a
roadmap project, P10, and its decision record is the discussion to have
first.
