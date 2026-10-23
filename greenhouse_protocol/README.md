# greenhouse-protocol

Canonical greenhouse records and the contracts that producers and consumers
implement. Part of [greenhouse-open](../README.md). Apache-2.0.

## Records

- `Observation`: one reading at one instant, of the greenhouse, a
  compartment or a plant, with its source.
- `Event`: something that happened (watering, harvest, spacing, a
  destructive sample), with a confidence and parameters.
- `MediaCapture`: an image by reference - sensor, instant, modality and
  where its bytes live. Pixels never go into a record.
- `CameraFrame`: a frame a camera took - instant, pose in the greenhouse's
  frame, intrinsics and the modalities it holds, with the captures holding
  its images when they are stored.
- `Sensor`: hardware, device id and calibrated intrinsics, and only what the
  source states about mounting.
- `GreenhouseDescription`, `Compartment`, `Plant`: what a producer states
  about a greenhouse's structure.
- **Acting on a greenhouse** (decision 0046):
  - `Action` (`actions`): what is to be done, to what, one union by kind;
  - `Plan` (`plan`): a run's planned actions, each with its timing, what it
    waits for, what to do if it is late, and its principal;
  - `AuthorisationConfig` (`authorisation`): who may do what, which a run's
    gateway enforces;
  - `ActionOutcome` (`outcome`): what became of each planned action;
  - `Assignment` and `ExecutionReport` (`assignment`): what a gateway and
    an executor exchange.

  Their JSON Schemas are published in the package (`schemas/`).
- `RequestedAction` (`action`) and the `ActionOutcome` of `execution`:
  deprecated, replaced by the above, and kept as they are until the
  simulator carries the new format out.

Chronology is the timestamp alone, always timezone-aware: every record
refuses a naive time (`greenhouse_protocol.instant.Instant`).

What was observed or happened cannot be edited: observations, events,
captures, frames and sensors are frozen. A greenhouse description, an action
and an outcome can be, by assigning a field, and each edit is checked as the
record was when built; a refused edit leaves the record as it was. A
description's plants, compartments and layout are values that an edit
replaces, so that the description checks it.

## Contracts (`greenhouse_protocol.contracts`)

- `canonical_store`: one store and one query contract per record kind.
  Every query takes `up_to`, the temporal-honesty boundary: a decision made
  at T must not see a record from after T.
- `execution`: how an approved action reaches whatever carries it out, and
  how an environment that cannot execute (a recorded history) refuses. Its
  `ActionExecutionAdapter` is deprecated: a run's gateway and its executors
  replace it (decision 0046).
- `conformance`: checks any producer's output must pass - unambiguous
  timestamps, unique identities, real numbers rather than placeholders -
  as plain functions returning a list of violations.
- `memory`: an in-memory reference implementation of the store and query
  contracts, precise about the semantics a real store must share.
- `consumer`: the interface a client reads a running producer through:
  `/consumer/v1` routes answering a run's identity, epoch and clock, its
  greenhouse description, and its observations and events after a cursor,
  in delivery order and never from the client's future. The rules a
  producer keeps (`check_batch`, `check_polls`) and a recorded exchange to
  develop a client against (`tests/fixtures/consumer/exchange.json`). The
  simulator is one producer of it; a gateway in front of real sensors is
  another.

## Dependencies

Pydantic 2 and the standard library.
