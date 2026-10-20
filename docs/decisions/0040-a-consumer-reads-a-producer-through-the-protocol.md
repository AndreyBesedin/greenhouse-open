# 0040: A consumer reads a running producer through the protocol's own interface

**Status:** Accepted
**Date:** 2026-10-20

## Context

Decision 0036 left the simulator's HTTP API to people: it shows the
simulated world, truth included, and said that the day a policy or an
application reads a running simulation, it gets an interface of its own
that serves observations and nothing else. That day has come: a downstream
application wants to follow a run as it advances, with the same code it
will later point at a real greenhouse's sensors.

Two shapes were weighed. The simulator could grow a second route table of
its own, which a client would imitate when it later reads a gateway in
front of real sensors; or the interface could belong to the protocol, with
the simulator as its first implementation and a gateway as its second, so
that one client reads either. The second keeps the boundary where this
repository draws every other one: records and contracts in
`greenhouse_protocol`, producers and consumers on either side of them.

The simulator's live run loops its scenario when it reaches the end, and a
deterministic run makes the same records, with the same identities, each
time round. A client that keyed only on record ids would see time go
backwards or silently overwrite a day with its own copy.

## Decision

- **The consumer interface is the protocol's**
  (`greenhouse_protocol.contracts.consumer`): routes under `/consumer/v1`
  answering a run's identity, epoch and clock, its greenhouse description,
  and its observations and events after a cursor. A producer implements
  it; the simulator is the first, behind a route surface separate from the
  viewer's, which serves no truth, no fields, no scene and no run state
  (P10.4). A breaking change is a new version segment.
- **A consumer reaches observed records only**, and the interface's checks
  hold a producer to what can be checked from outside: dense cursor
  positions, delivery order, nothing from after the run's clock, repolls
  that extend and never rewrite, no record twice in an epoch, a clock that
  never turns back within one, and records of the run's greenhouse only.
- **A run has epochs.** A timeline that starts over, by looping, restart or
  re-initialisation, is a new epoch of the same run, never a step back in
  time; a consumer keys what it stores by run, epoch and record id. A stale
  cursor is answered empty in the current epoch, and the client starts
  again from zero.
- **Delivery order, not timestamp order.** The logs a cursor walks are in
  the order records reached the producer, so a late reading appears when it
  could first have been known, and a consumer that follows the cursor
  never learns anything earlier than the producer did.
- **A recorded exchange is the fixture** a client is developed against and
  a producer's answers are compared with, written by the protocol's own
  test from the protocol's own records, with no producer involved.

## Consequences

- A downstream application's client is one piece of code for the simulator
  and for a future gateway, and depends on the protocol alone.
- The simulator gains a consumer route surface (P10.4) and a decision on
  which run it serves (P10.2); until then the fixture is the only producer.
- Actions in, through the same interface, are a later version: nothing
  here lets a client change a run.
- Worth revisiting if a producer cannot keep dense positions or delivery
  order, which would mean the cursor should name a record rather than a
  count.
