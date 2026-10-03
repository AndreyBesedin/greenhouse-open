# greenhouse-sim viewer

The browser viewer for the simulator. It is an adapter around the headless
simulator core: it displays what the simulator produces, and the simulator
never depends on it. For now it is a bootstrap page that identifies itself
and the build; scenes arrive with the browser renderer (P00 in the
[simulator roadmap](../../docs/roadmap/README.md)).

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
