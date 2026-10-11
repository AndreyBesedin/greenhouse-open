# 0029: Test hooks and components mounted, in a DOM, file by file

**Status:** Accepted
**Date:** 2026-10-11

## Context

Decision 0010 runs the viewer's unit tests in Node. Its component tests
render static markup, which runs no effect, subscription or clean-up. The
frontend audits (FE-AUDIT.3) found the viewer's asynchronous behaviour
tested only through the browser: switching or leaving a live stream, a retry
waiting, and an answer arriving after the request has changed. The command
race of FE-AUDIT.1 showed why that is not enough.

Testing a hook needs a mounted component, and so a DOM. The options were a
DOM for every test, or for the files that need one; and a testing library,
or React's own `act` and `createRoot`.

## Decision

- **jsdom** is a dev dependency. A test file that mounts a component or runs
  a hook asks for it with `// @vitest-environment jsdom` on its first line.
  Every other test file stays in Node, as 0010 has it.
- Hooks are mounted by `src/testing/renderHook.tsx`, a small helper on
  React's `act` and `createRoot`, with no testing library.
- A test that drives a browser API the DOM does not have, such as
  `EventSource`, stands in a fake for it (`vi.stubGlobal`), and drives time
  with Vitest's fake timers.

This supersedes 0010's "Vitest runs unit tests in Node" for those files
only.

## Consequences

- Effects, clean-ups and stale answers are tested where they are written:
  `useLoad` and `useLiveScene` first.
- A file in the DOM environment takes about half a second more to start,
  in parallel with the others: with the first two, the unit tests went from
  1.8 s to 2.0 s on a developer's machine.
- jsdom's `URL` is not one Node's `fs` takes, so a test in it reads its
  fixtures by path (`fileURLToPath(import.meta.url)`).
- If mounted component tests come to outnumber static ones, or need user
  events and queries by role, a testing library may be worth its dependency.
