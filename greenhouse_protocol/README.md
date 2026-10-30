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

  Their JSON Schemas are published in the package (`schemas/`). They
  replace the first action format, `RequestedAction` and its outcome,
  removed in P13.9.
- **What a policy decides with** (decision 0061):
  - `CapabilityContext` (`context`): what a principal may read and do in
    a run: its observation sources, devices, targets, crop instances,
    when each kind of action is carried out, the gateway's limits, its
    grants, and an experiment's goals;
  - `InformationBudget` (`budget`): the forecast providers and prediction
    assets it is given beyond the observations and the clock, labelled an
    oracle exactly when any of them is the simulated world's truth;
  - `Forecast` (`forecast`): a provider's forecast of a quantity, for a
    moment or a period, with its issue time and its uncertainty.

  Their JSON Schemas are published beside the others.

Chronology is the timestamp alone, always timezone-aware: every record
refuses a naive time (`greenhouse_protocol.instant.Instant`).

What was observed or happened cannot be edited: observations, events,
captures, frames and sensors are frozen, and so are the records of acting
on a greenhouse: actions, plans, outcomes, assignments, reports and
authorisation configurations. A greenhouse description can be, by
assigning a field, and each edit is checked as the record was when built; a
refused edit leaves the record as it was. A description's plants,
compartments and layout are values that an edit replaces, so that the
description checks it.

## Contracts (`greenhouse_protocol.contracts`)

- `canonical_store`: one store and one query contract per record kind.
  Every query takes `up_to`, the temporal-honesty boundary: a decision made
  at T must not see a record from after T.
- `gateway` (decision 0046): a run's gateway, its local endpoint, which
  holds the run's plan, schedules it, applies lateness, authorises and
  writes the outcome log (`RunGateway`), with its routes under
  `/actuation/v1`, the rules it keeps, and `check_gateway`, which holds a
  gateway to them through a harness that moves its clock.
- `execution`: an executor behind a gateway (`ActionExecutor`), which
  carries an assignment out at most once, may be revoked before it starts,
  and is asked how an assignment stands when its report does not come;
  `check_executor` holds one to that, with an action of a kind it carries
  out: by default the first it names, or one given. How an environment that cannot
  execute (a recorded history) refuses: `ActionNotExecutable`.
- `memory_gateway`: an in-memory reference implementation of the two, a
  gateway on a clock that continues and an executor into which faults can
  be injected (a lost send, an executor that cannot be reached), to
  develop a gateway or an executor against.
- `conformance`: checks any producer's output must pass - unambiguous
  timestamps, unique identities, real numbers rather than placeholders -
  as plain functions returning a list of violations.
- `memory`: an in-memory reference implementation of the store and query
  contracts, precise about the semantics a real store must share.
- `policy` (decision 0061): a policy's port (`PolicyPort`), what a control
  policy reads of a run and gives it, as its own principal: its context,
  its budget, the observations of its context's sources, the events with
  the parameters their types allow, the outcomes and plans of its own,
  and its budget's forecasts, each no earlier than issued; and nothing of
  the simulated world's truth. Its routes under `/policy/v1`; what it may
  read, field by field (`READABLE_FIELDS`, `READABLE_EVENT_PARAMETERS`),
  which `check_readable` holds its records to; the `Policy` an
  experiment's runner steps, given a `Delivery` and answering a
  `Decision`; and `check_policy_port`, which holds a port to the contract
  through a harness that moves its run.
- `memory_policy`: an in-memory reference implementation of a policy's
  port, on the in-memory gateway, to develop a port against.
- `consumer`: the interface a client reads a running producer through:
  `/consumer/v1` routes answering a run's identity, epoch and clock, its
  greenhouse description, and its observations and events after a cursor,
  in delivery order and never from the client's future, and the outcomes of
  the actions a run's gateway carried out or not, as a third log. The rules a
  producer keeps (`check_batch`, `check_polls`) and a recorded exchange to
  develop a client against (`tests/fixtures/consumer/exchange.json`). The
  simulator is one producer of it; a gateway in front of real sensors is
  another.

## Dependencies

Pydantic 2 and the standard library.
