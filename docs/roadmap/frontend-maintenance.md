# Frontend audit follow-up and maintenance

**Priority:** medium for the planned work below.
**Schedule:** an explicit maintenance window after P07, before P09's
integrated release QA: a second frontend audit of the viewer as it stands
then, followed by the remaining findings below, the second audit's, and
general clean-up together. They do not block P02–P07. A reproduced defect
affecting those projects can be brought forward as a focused fix.

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
| FE-AUDIT.6 | API bind failure masks the original exception | Medium | Planned, after P07 |
| FE-AUDIT.7 | Small organizational, test-quality and telemetry improvements | Medium | Planned, general refactoring after P07 |

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
