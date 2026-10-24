# 0052: A simulator's authorisation is a file it is given, the local operator's by default

**Status:** Accepted
**Date:** 2026-10-24

## Context

Decision 0046 puts authorisation in the design of acting on a greenhouse.
Every planned action carries its principal, groups grant kinds of action,
optionally on targets, and the gateway alone enforces them, when a plan is
given and when each action falls due. It leaves the groups to the
deployment: the simulator ships the local operator's.

P13.3 made a playback the gateway of its run, and gave its gateway one
fixed authorisation, the local operator's, allowed every kind. P13.4 makes
the authorisation an input of the run, its changes recorded, and binds a
plan's principals to whoever submits it.

The simulator's local API answers only on this machine (decision 0009) and
knows no users: it authenticates no one. A platform that serves people of
its own, such as a downstream application, authenticates them itself and
reaches the simulator as one submitter.

## Decision

- **The authorisation is the protocol's record**
  (`greenhouse_protocol.authorisation.AuthorisationConfig`): its version,
  its groups and their grants. A simulator holds one, which every playback's
  gateway enforces.
- **The server is given it as a file**, `--authorisation <file>`, a JSON
  document as the protocol writes the record. One that cannot be read, or
  is not the record, stops the server starting, saying why. Without the
  option, the authorisation is the local operator's: the person at the
  simulator's own interface, `person:local_operator`, may do every kind.
- **The local API's submitter is the local operator.** Whatever reaches the
  local API acts as it. A plan's action proposed for anyone else is refused
  unless the authorisation grants the local operator to propose on their
  behalf. A platform's own people are its own to authenticate: it submits
  as the principal it is granted to be, proposing for them as its grants
  allow.
- **A change is recorded.** A simulator given another authorisation while
  its runs play (`Simulator.authorise`) has every playback's gateway
  enforce it from its clock's moment on. The gateway records the change,
  with its version and moment, beside each plan (`PlanState.authorisation`).
  An action whose rights are withdrawn before it falls due is refused then,
  saying so, and the run goes on without it. A playback started afterwards
  takes the new authorisation from its start.

## Consequences

- A simulator served for more than its local operator is configured by a
  file, versioned as the protocol's record is, and reviewed as a file is.
- Nothing in the local API authenticates. Serving the simulator beyond this
  machine would need authentication of its own: a decision of its own.
- P13.7's routes give and change plans as the local operator. A route to
  change the authorisation itself is left out: it is the server's input.
