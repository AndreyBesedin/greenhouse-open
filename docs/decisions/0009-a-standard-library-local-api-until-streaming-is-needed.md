# 0009: A standard-library local API until streaming is needed

**Status:** Accepted
**Date:** 2026-10-03

## Context

The browser viewer needs to reach the simulator, which runs in Python. P-1.8
asks only for a health check, version metadata, the scenario registry and an
initial scene. Streaming scene updates arrives with P00, when Python starts
driving the scene. The simulator's dependency test allows a package to import
only what it declares, and the simulator core must run without a server.

## Decision

- The local API is `greenhouse_sim.api`, built on the standard library's
  `http.server`. It adds no dependency to `greenhouse-sim`.
- It binds to the loopback interface, answers GET only, and returns JSON. It
  is a developer tool on one machine, not a service.
- Routing is a plain function from method and path to status and body, so it
  is tested without sockets, and the HTTP server is a thin shell around it.
- The viewer's development and preview servers forward `/api` to it, so the
  page and the API share an origin and the API sends no cross-origin headers.
- The API owns no simulation logic and serves no ground truth. Nothing else in
  the package imports it, and a simulator run never loads it. Tests enforce
  both.
- A web framework (with WebSocket or server-sent events) replaces the
  standard-library server when P00 needs streaming. It is then declared as an
  optional dependency of the API, so the core stays dependency-free.

## Consequences

- `pip install greenhouse-sim` still brings only its declared runtime
  dependencies, and the API works out of the box.
- The standard-library server is not hardened for exposure beyond the local
  machine, which is acceptable because it binds to loopback only.
- Moving to a framework later changes `api/server.py` and the dependency
  declaration. The routes and their tests carry over.
