# 0008: Build the viewer with npm, Node 24, Vite and strict TypeScript

**Status:** Accepted
**Date:** 2026-10-03

## Context

The browser viewer (P-1.7 onwards) brings a JavaScript toolchain into a
repository whose packages are Python. The roadmap fixes the application
stack: React, TypeScript, and Three.js through React Three Fiber. Still open
were the package manager, the Node version, the build and test tools, and how
the viewer is versioned alongside the simulator it ships with. The guiding
rule for tooling is to add as little as the work needs and to replace working
tools only for a clear gain.

## Decision

- **npm**, which ships with Node, so contributors install nothing extra. The
  lockfile `package-lock.json` is committed and `npm ci` installs from it.
- **Node 24**, the current long-term-support release, pinned in `.nvmrc` and
  required through `engines`.
- **Vite** builds and serves the viewer, and **Vitest** tests it with Vite's
  own configuration.
- **TypeScript in strict mode**, with unchecked index access and exact
  optional properties also checked. `npm run build` fails on a type error.
- **The viewer has no version of its own.** It reads the simulator's version
  from `greenhouse_sim/pyproject.toml` at build time and reports that version
  and the commit it was built from.
- The viewer lives in `greenhouse_sim/web`, outside the Python package, so it
  is not part of the wheel and nothing in the simulator imports it.

Linting and formatting for TypeScript, and CI for the viewer, are decided in
P-1.9, together with the rest of the viewer's checks.

## Consequences

- Python and TypeScript tooling stay separate. Each package is checked with
  its own tools, as the Python packages already are.
- A simulator release and the viewer built from the same commit always report
  the same version.
- Moving to another package manager later means replacing the lockfile and
  CI steps, nothing in the code.
