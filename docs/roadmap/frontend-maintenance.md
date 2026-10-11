# Frontend audit follow-up and maintenance

**Priority:** medium for the planned work below.
**Schedule:** an explicit maintenance window after P07, before P09's
integrated release QA: a second frontend audit of the viewer as it stands
then, followed by the remaining findings below, the second audit's, and
general clean-up together. They do not block P02–P07. A reproduced defect
affecting those projects can be brought forward as a focused fix. The window
opened on 2026-10-11, after P08 and before P09: the
[second audit](#second-audit-after-p08) and its
[order of work](#order-of-work) are below.

Part of the [simulator roadmap](README.md). These maintenance identifiers
track audit findings separately from the simulator's project steps.

## Audit provenance

The audit was made on **2026-10-06**, during **P01.3: pitched roof geometry**:
P-1 and P00 were complete, P01.1–P01.3 had been delivered, and P01.4–P01.7
and the final `greenhouse-shell` QA were still planned.

- Initial inspected commit:
  [`ef885b736cf273ca5a951c1b2e551562ade55374`](https://github.com/AndreyBesedin/greenhouse-open/commit/ef885b736cf273ca5a951c1b2e551562ade55374)
  (`docs: describe the pitched roof and picking through glass, mark P01.3 done`).
- Frozen committed snapshot used to finish browser verification:
  [`bfc8672a4547939973b2f41726dae331e01fb527`](https://github.com/AndreyBesedin/greenhouse-open/commit/bfc8672a4547939973b2f41726dae331e01fb527)
  (the P01.3 merge, with the same project execution stage).
- The two immediate fixes (FE-AUDIT.1 and .2) followed the same day, on top
  of P01's completion,
  [`e57057eba7e5043f2f5b56eee14bd50a75aa41dd`](https://github.com/AndreyBesedin/greenhouse-open/commit/e57057eba7e5043f2f5b56eee14bd50a75aa41dd).

## Assessment and evidence at the audit

The frontend was well structured for a small simulator viewer. Keep its
architecture and improve specific weaknesses rather than rewrite it.

- Strict TypeScript, including unchecked index access and exact optional
  properties, and discriminated unions for sources and loading/error states.
- Generated scene types, runtime AJV validation, and a typed renderer registry
  requiring handling of new entity kinds.
- Clear boundaries between scene data, rendering and UI. Selection,
  transforms, dimensions and colouring are mostly pure functions. Shape and
  overlay primitives are reusable; UI components mostly use explicit props
  and callbacks. The flat folder structure is appropriate at this size.
- Explicit graphics-resource disposal and effective cylinder instancing.
- Useful tests of geometry, glass picking, schema rejection, deterministic
  scenes, instancing, reconnecting and real simulator controls.
- Biome lint/formatting, strict TypeScript, 129 unit tests in 17 files and
  the production build passed. All 20 existing browser tests passed against
  the frozen committed snapshot. Two additional browser probes reproduced
  findings 1 and 2; passing probes demonstrated the defects, not fixes.
- Canonical Python fast checks passed: lint, formatting, typing and 356
  tests. Linux screenshot comparisons and GPU benchmarks were not run.
- The production JavaScript bundle was about 1,318 kB minified / 364 kB
  gzip. The local-tool context and Three.js cost are documented in Vite's
  configuration; this alone is not evidence of a performance defect.

## Follow-up work

| Identifier | Finding | Priority | Status / schedule |
| --- | --- | --- | --- |
| FE-AUDIT.1 | Obsolete command responses change another source's feedback | Medium | Addressed in this follow-up |
| FE-AUDIT.2 | Floating panels overlap in smaller windows | Medium | Addressed in this follow-up |
| FE-AUDIT.3 | React hook and async lifecycle coverage is thin | Medium | Planned, after P07 |
| FE-AUDIT.4 | Coverage is neither measured nor enforced | Medium | Planned, after P07 |
| FE-AUDIT.5 | Local browser tests can reuse stale servers | Medium | Planned, after P07 |
| FE-AUDIT.6 | API bind failure masks the original exception | Medium | Addressed in the maintenance window, step 1 |
| FE-AUDIT.7 | Small organizational, test-quality and telemetry improvements | Medium | Planned, general refactoring after P07 |
| FE-AUDIT.8 | Every load is written out by hand | Medium | Second audit; planned with FE-AUDIT.3 |
| FE-AUDIT.9 | The address is written in six places | Medium | Second audit; planned before P09 |
| FE-AUDIT.10 | A climate run's request is assembled three times | Medium | Second audit; planned before P09 |
| FE-AUDIT.11 | `App` draws every panel itself | Medium | Second audit; planned with FE-AUDIT.7 |

Findings 5 and 6 were low severity in the original audit; their planned work
has medium priority here. Severity describes impact; priority describes
when the work should be scheduled.

### FE-AUDIT.1: Command feedback belongs to its source and request

Sending a command in scenario A, switching to B and receiving A's delayed
failure displayed that failure in B's HUD. Clearing feedback on source change
did not invalidate the pending promise. Older requests could also overwrite
newer feedback in the same scenario.

The follow-up invalidates command feedback on source changes and unmount,
and accepts results only from the latest command generation. Regression
checks cover switching sources, returning to the original scenario before a
response arrives, and older successes/failures arriving after a newer failure.
This controls displayed feedback; it does not undo a command already sent to
the simulator.

### FE-AUDIT.2: Panels remain separate and reachable

Fixed corner positions and largely fixed widths caused overlap at 640 × 480.
The existing resize test checked the canvas size without checking whether its
controls remained usable.

The follow-up stands the panels in two independent columns at the sides of
the view: the info panel above the inspector on the left, the HUD above the
legends on the right. A column shares its height among its panels, which
scroll rather than overlap when they do not all fit, and keep the widths they
had when they floated. A first version split the view into a two-by-two
grid instead, which capped the info panel at half the window's height even
with no inspector below it, and let a tall legend on the right crop it. At
widths up to 840 px, the columns dissolve into a scrollable bottom dock
occupying at most 45% of the view's height. The upper canvas remains
available for orbiting and picking. Inspector and legends join the same flow
rather than covering other controls. Browser regression checks cover
1280 × 720, 1000 × 480, 640 × 480 and 360 × 640, including selecting an
entity, changing overlays, reaching a legend and clearing selection; and, at
1280 × 720 beside the tallest legend, that the info panel shows all of itself
and the HUD keeps its width.

### FE-AUDIT.3: Test async behavior at its owning boundary

Static React rendering does not exercise effects, subscriptions or callbacks.
Normal streaming and reconnecting were covered in the browser, but
`useLiveScene` had no direct lifecycle tests. The command race showed why
happy-path checks were insufficient.

Acceptance:

- Test stream switching and unmount cleanup, including a pending retry timer.
- Test invalid frames followed by valid-frame recovery.
- Test delayed scene responses after source changes, and response ordering.
- Prefer mounted hook/component tests with controlled EventSource, fetch and
  timers where they explain the failure better than a full-stack walkthrough.
- Retain focused browser checks of integration with the real simulator.

### FE-AUDIT.4: Establish meaningful coverage reporting

129 passing tests did not establish a coverage percentage or complete
behavioral coverage. No coverage report or threshold was configured.

Acceptance:

- Report coverage for handwritten production code; exclude generated
  contracts and test files explicitly.
- Inspect uncovered branches in networking and state transitions first.
- Record the initial baseline, then set justified thresholds in CI.
- Require tests of observable behavior, not assertions added only to raise a
  percentage. Do not duplicate implementation logic in tests.

### FE-AUDIT.5: Make local E2E server selection reproducible

Playwright reused existing API/preview servers outside CI. During the audit,
that reached an old simulator and produced seven unrelated failures. CI
already disabled reuse.

Acceptance:

- Use dedicated test ports and fresh servers, or verify compatibility before
  reuse. Make deliberate reuse explicit rather than silently trusting health.
- Ensure the API and preview are from the intended checkout/build.
- Demonstrate that an unrelated running development server cannot change a
  local test result; document the canonical local command.

### FE-AUDIT.6: Preserve errors during partial API initialization

`SimulatorServer` initialized its superclass before assigning `self.live`.
If binding failed, superclass cleanup called `server_close()`, which accessed
that missing attribute and raised `AttributeError`, masking the bind failure.
This was observed under socket restrictions and also applies to other bind
failures such as an occupied port.

Acceptance:

- Make cleanup safe for a partially initialized server without leaking a
  socket or starting live-run resources unnecessarily.
- Test a bind failure and assert that its original exception is preserved.
- Keep the existing normal shutdown/live-run cleanup behavior covered.

Addressed in step 1 of the maintenance window. `SimulatorServer` makes its
live runs before it binds. A run starts only when a viewer first asks for
one, so a server that fails to bind has none to stop, and raises the bind's
own error. `test_a_port_already_taken_is_reported_as_such` binds a second
server to a port in use and expects `EADDRINUSE`; it failed with the
`AttributeError` before the change. Closing a server still stops its live
runs, as `test_closing_the_server_stops_its_live_runs` checks.

### FE-AUDIT.7: General refactoring after P07

Review the frontend as it exists after P07 before choosing the size of these
changes. The original audit recommended small improvements, not a framework
migration or a global state library.

- Extract scene loading and command handling from `App` when those ownership
  boundaries improve clarity; preserve source switching and opening controls.
- Consolidate repeated panel presentation styles with a small shared pattern.
- Keep static-render tests for presentation, but replace brittle exact-HTML
  assertions with semantic queries and mounted interaction tests for controls.
  `Hud.test.tsx` and `scene/live.test.tsx` contain representative markup-string
  assertions that can fail on harmless changes while missing broken handlers.
- Remove unnecessary type escapes in tests, including `gable as never` in
  `Inspector.test.tsx`; use properly typed fixtures so tests respect contracts.
- Profile telemetry updates: HUD samples rerendered `App` four times per
  second and pointer updates could occur more often. Isolate that state if
  profiling shows meaningful work in scene/UI descendants. This was an
  optimization opportunity, not a measured performance defect.
- Preserve pure domain functions, renderer reuse, runtime validation and
  graphics-resource cleanup. Keep behavior changes separate from mechanical
  moves, and rerun browser/visual checks appropriate to each change.

## Second audit, after P08

The second audit was made on **2026-10-11**, at
[`2e874ed74`](https://github.com/AndreyBesedin/greenhouse-open/commit/2e874ed)
(the merge of P08's final QA, #112): P00–P08 complete, P09 not started.

### Assessment and evidence

The architecture the first audit found still holds, and the viewer has grown
along it. What has not kept pace is `App`, which every project since has
extended in place.

- Biome, the strict type check and the production build passed. Unit tests:
  334 in 50 files, against 129 in 17.
- The handwritten source is about 17,200 lines, in folders by area
  (`fields`, `sensors`, `weather`, `plants`, `cfd`, `qa`, `scene`, `debug`),
  which have replaced the flat structure the first audit found.
- API answers still go through one fetch wrapper, and are checked before
  use.
- `App.tsx` is 1,119 lines, with 33 pieces of state; it was 164 lines at the
  first audit.
- The production bundle is 1,458 kB minified, 406 kB gzip (1,318 kB and
  364 kB at the first audit).
- No unit test mounts a component or runs a hook: Vitest runs in Node, and
  the 16 component test files render static markup. They hold 96 assertions
  on markup strings.
- Five commits since 2026-10-01 gave browser tests longer to wait for a
  climate run's answer (`0d8ce6c`, `92bf66c`, `6c1e045`, `0441c98`,
  `61b2bd2`). The waits are for the simulator's runs, not the viewer's
  rendering, and belong with the roadmap's test-suite and CI time work after
  P09.

### The first audit's findings, now

- **FE-AUDIT.3** is open, and wider. `useLiveScene` still has no lifecycle
  tests, and the guard against a stale answer, tested nowhere, is now
  written out fourteen times in `App` and in eight components
  (FE-AUDIT.8).
- **FE-AUDIT.4** is open: no coverage is configured.
- **FE-AUDIT.5** is open. The browser and screenshot configurations reuse a
  running server outside CI, and the benchmark's always does. Local runs
  work around it by editing `simulatorApi.ts` to another port and back.
- **FE-AUDIT.6** was open, unchanged in `greenhouse_sim/api/server.py`;
  step 1 addresses it.
- **FE-AUDIT.7** is open. Most of its `App` work is now FE-AUDIT.8–11.
  `gable as never` remains in `Inspector.test.tsx`, with `as unknown as` in
  two more test files and, after validation, twice in `weather/weather.ts`.
  `Hud.test.tsx` still asserts on markup strings.

### FE-AUDIT.8: Every load is written out by hand

Each thing `App` loads for a scene (its field, a compared field, the
weather and its day, the probes' charts, the house's air, the glazing, the
openings' flows, the CFD boundaries, the plants' light and two sensor logs)
has its own effect. Each sets its state loading unless something is already
on show, loads, and drops the answer if its inputs changed meanwhile. Eight
components do the same. A change to that pattern, such as cancelling the
request, has to be made in every copy.

Acceptance:

- One hook owns loading, keeping the last answer on show and dropping stale
  answers, and is tested mounted, as FE-AUDIT.3 asks.
- `App` and the components use it; their effects become a call each.

### FE-AUDIT.9: The address is written in six places

`setScenarioSource` writes the address and the source together, but opening
changes, the plant lab's runs, its play, the climate run's moment and a
source chosen each call `history.replaceState` themselves.

Acceptance: one owner of the source and its address; nothing else writes
the address.

### FE-AUDIT.10: A climate run's request is assembled three times

The field, the compared field and the sensors' logs each rebuild the run's
changes (layout, levels, openings, schedule, moment and weather) from
strings, which `App` keeps so that the effects' dependencies compare by
value (`pairsText`, then `pairsFrom`). The other loads build their address
from the source instead.

Acceptance: one value describes the climate run drawn, compared by its
address, and every load of it starts from that value.

### FE-AUDIT.11: `App` draws every panel itself

The scenario's, the climate run's and the plant lab's panels are written
inline in `App`, with `source.field === CLIMATE_FIELD` tested eleven
times. P09 adds an event timeline, a QA mode and branch charts, which need
somewhere other than `App` to go.

Acceptance: the scenario, climate-run and plant-lab panels are components
of their own, given what they draw; `App` composes them.

## Order of work

Each step is a pull request, stacked on the one before, and none changes
what the viewer shows: the browser tests and screenshots pass unchanged.

1. **FE-AUDIT.6**, the API's bind failure: small, and on the Python side.
2. **FE-AUDIT.5**, browser tests on their own servers: the local
   workaround goes.
3. **FE-AUDIT.3 and .8**: mounted tests in a DOM environment, the loading
   hook, and `useLiveScene`'s lifecycle tests. Unit tests in a DOM
   environment depart from decision 0010's Vitest in Node, so this step
   records a decision.
4. **FE-AUDIT.9 and .10**: the source and its address, and the climate run.
5. **FE-AUDIT.11 and .7**: `App`'s panels, the telemetry profiled, the
   panels' shared styles, and the tests' type escapes and markup strings.
6. **FE-AUDIT.4**: coverage, its baseline and thresholds, last, so that the
   baseline counts the new tests.
