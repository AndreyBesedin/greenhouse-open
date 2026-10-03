# greenhouse-sim viewer

The browser viewer for the simulator. It is an adapter around the headless
simulator core: it displays what the simulator produces, and the simulator
never depends on it. For now it identifies itself and its build, and lists
the simulator's scenarios; scenes arrive with the browser renderer (P00 in
the [simulator roadmap](../../docs/roadmap/README.md)).

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
npm test            # Vitest
npm run typecheck   # TypeScript, strict
npm run build       # production build into dist/
```

The page shows the simulator version, read from `../pyproject.toml` at build
time, and the commit it was built from. The viewer has no version of its own:
it ships with the simulator.

Built with React, TypeScript and Vite. The 3D scene will use Three.js through
React Three Fiber, as the roadmap's technical choices describe.
