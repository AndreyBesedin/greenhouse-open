# 0012: Stream to the viewer with Server-Sent Events

**Status:** Accepted
**Date:** 2026-10-03

## Context

Decision 0009 built the local API on the standard library's HTTP server, and
planned to replace it with a web framework (with WebSocket or server-sent
events) once P00.4 needed streaming, declared as an optional dependency of the
API.

P00.4 needs one direction only: the simulator sends a scene each simulated
day, and the viewer follows. The commands planned for P00.5 (play, pause,
step, speed, reset) are occasional requests from the viewer, not a stream.
The browser's `EventSource` already reconnects after a network error, which is
exactly what "restart the backend, the browser reconnects" asks for. An
optional dependency also needs care with the dependency test, which only knows
a package's required dependencies.

## Decision

- Live scenarios stream as Server-Sent Events from the existing
  standard-library server: `GET /api/scenarios/{id}/live` sends a `frame`
  event per simulated day, a reconnect hint, and keep-alive comments.
- Commands from the viewer, from P00.5 on, are plain HTTP requests (POST) on
  the same server.
- The viewer reconnects by itself where `EventSource` gives up, after an error
  response such as a proxy's 502.
- The API still adds no dependency to `greenhouse-sim`.
- A framework is reconsidered only when a need appears that this cannot meet,
  such as two-way streaming, many concurrent viewers, or serving beyond the
  developer's machine.

This replaces the streaming plan in decision 0009. The rest of 0009 stands.

## Consequences

- Installing `greenhouse-sim` still brings only its declared dependencies, and
  the viewer works against it out of the box.
- Each open stream holds one server thread, which is fine for a local
  development tool.
- Moving to a framework later changes `api/server.py`. The routes, the live
  runs and their tests carry over.
