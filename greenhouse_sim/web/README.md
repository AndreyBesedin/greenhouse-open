# greenhouse-sim viewer

The browser viewer for the simulator. It is an adapter around the headless
simulator core: it displays what the simulator produces, and the simulator
never depends on it. It shows a full-window 3D view (for now a reference
scene: a 1 m grid on the ground, the world axes and a 1 m cube) with a panel
listing its build and the simulator's scenarios, and a HUD.

Drag to orbit, right-drag to pan, and scroll to zoom. The HUD's buttons jump
to the top, front, side and isometric views; a refresh always returns to the
isometric one. It also shows the camera's position and where the pointer
meets the ground, both in world metres, with the frame rate and object
count. The browser renderer is
being built out in P00 of the [simulator roadmap](../../docs/roadmap/README.md).

The view uses the simulator's world axes: metres, right-handed, z up. Three.js
is y up, so `src/world.ts` converts once, at the root of the scene; nothing
else in the viewer deals with the difference.

## Run it with the simulator

The viewer reads the simulator through its local API. Start the API, then the
viewer, in two terminals:

```bash
python -m greenhouse_sim.api          # http://127.0.0.1:8765/api
cd greenhouse_sim/web && npm run dev  # the viewer, which forwards /api there
```

Without the API, the page says so and how to start it.

## Develop

Node 24 (see `.nvmrc`) and npm.

```bash
cd greenhouse_sim/web
npm ci
npm run dev         # local development server
npm run lint        # Biome: formatting and lint (npm run format applies fixes)
npm run typecheck   # TypeScript, strict
npm test            # Vitest
npm run build       # production build into dist/
PYTHON=python npm run e2e  # Playwright smoke test against the real simulator API
```

The smoke test starts the simulator's API with `$PYTHON -m greenhouse_sim.api`,
so that interpreter needs greenhouse-sim installed. Run
`npx playwright install chromium` once to get the browser.

The page shows the simulator version, read from `../pyproject.toml` at build
time, and the commit it was built from. The viewer has no version of its own:
it ships with the simulator.

Built with React, TypeScript and Vite. The 3D scene will use Three.js through
React Three Fiber, as the roadmap's technical choices describe.
