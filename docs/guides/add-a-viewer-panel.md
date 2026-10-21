# Add a viewer panel with its loader

The viewer (`greenhouse_sim/web`) only shows what the simulator serves: a
panel is a loader that asks one of the API's routes and checks its answer,
and a component that draws it. If the route does not exist yet, start with
[an API route and its service](add-an-api-route.md). The timeline's panel
(commit `bf5eb31`) is the example of one that loads when it is opened; the
Move panel (`greenhouse_sim/web/src/MovePanel.tsx`) of one in the inspector,
for the selected item.

## Steps

1. **The loader**, a module beside its subject, such as
   `greenhouse_sim/web/src/timeline/timeline.ts`:
   - the answer's shape as a camelCase interface, and its state as a union:
     none, loading, unavailable with a reason, or loaded;
   - its URL, built from the run with `scenarioUrl` and `runParameters`
     (`greenhouse_sim/web/src/scene/run.ts`), so that it asks for the run
     the view shows;
   - a `parse` function that reads the body with its contract's reader,
     `contractReader(SCHEMA, "… is not what the viewer expects")`
     (`greenhouse_sim/web/src/loadJson.ts`), and turns the snake_case
     answer into the camelCase interface; and a `load(url, fetchFn =
     fetch)` that asks with `loadJson`, which turns a refusal into "the
     simulator API answered N". The route's answer is published as a
     schema first ([an API route](add-an-api-route.md)).
2. **The panel**, such as
   `greenhouse_sim/web/src/timeline/TimelinePanel.tsx`. Either it loads its
   own data when it is opened, with `useLoad`
   (`greenhouse_sim/web/src/useLoad.ts`) and nothing asked while it is
   closed, or `greenhouse_sim/web/src/App.tsx` loads the data, because the
   scene needs it too, and passes it down. `useLoadProgress` keeps what was
   last drawn while the next answer is on its way.
3. **Its place:** among the scenario's panels in
   `greenhouse_sim/web/src/ScenarioPanels.tsx`, in its order; in the
   inspector (`greenhouse_sim/web/src/Inspector.tsx`), for a selected item;
   or folded to its summary line with `greenhouse_sim/web/src/folds.ts`.
4. **Its styles** in `greenhouse_sim/web/src/styles.css`, in a commented
   block, with colours only as the panels' `var(--panel-…)` tokens, which
   `greenhouse_sim/web/src/styles.test.ts` checks.
5. **Unit tests** beside it, such as
   `greenhouse_sim/web/src/timeline/timeline.test.tsx`: the URL it asks
   for, a body parsed and one refused, a failed answer, and the markup
   (`renderToStaticMarkup`), or clicks with
   `greenhouse_sim/web/src/testing/render.tsx`.
6. **A browser test**, such as `greenhouse_sim/web/e2e/timeline.spec.ts`:
   the view opened at a moment, the panel opened, and what it says
   checked step by step. A slow spec runs on its own, in `ONE_BY_ONE` in
   `greenhouse_sim/web/playwright.config.ts`.
7. **The README:** a paragraph in `greenhouse_sim/web/README.md` naming the
   panel and the route it reads.

## Tests

```bash
cd greenhouse_sim/web && npx vitest run src/timeline   # its own tests, while working
uv run viewer-checks                                   # lint, types, every unit test, coverage, build
uv run browser-tests e2e/timeline.spec.ts              # TEST_PORT_OFFSET=20 beside another checkout
```

## What else to know

- **Coverage** has floors (`greenhouse_sim/web/vite.config.ts`), and
  `App.tsx` is barely covered by unit tests: keep the logic in a module
  its tests reach.
- **Browser tests share one simulator API** and are retried once on CI, so
  a spec passes on its first try and also on a retry that finds what the
  first one left.
- **CI draws in software,** at a few frames a second: long specs set their
  own timeout, and screenshot baselines are drawn by CI only.
- **A contract** is listed in
  `greenhouse_sim/web/scripts/generateContractSources.ts`; `npm run
  generate` writes its types and schema into its area's `generated/`
  folder, and `greenhouse_sim/web/src/contracts.test.ts` fails when they
  drift.
