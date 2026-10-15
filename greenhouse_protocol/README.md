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
- `RequestedAction` and `ActionOutcome`: what someone wants done, and what
  happened when an executor tried.

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
  how an environment that cannot execute (a recorded history) refuses.
- `conformance`: checks any producer's output must pass - unambiguous
  timestamps, unique identities, real numbers rather than placeholders -
  as plain functions returning a list of violations.
- `memory`: an in-memory reference implementation of the store and query
  contracts, precise about the semantics a real store must share.

## Dependencies

Pydantic 2 and the standard library.
