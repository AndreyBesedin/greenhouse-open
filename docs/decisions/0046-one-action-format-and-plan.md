# 0046: One action format, and a plan a run's gateway carries out

**Status:** Proposed. It becomes Accepted, or is changed, in the pull
request that starts its implementation (P13.1, [P13](../roadmap/p13-actions.md)).
**Date:** 2026-10-22

## Context

The protocol says how a greenhouse is acted on: a policy proposes an
action, an executor validates and carries it out, and an outcome comes
back (`greenhouse_protocol/action.py`, `greenhouse_protocol/execution.py`,
`greenhouse_protocol/contracts/execution.py`). Decision 0035 says the same
of the simulator: "a policy drives the run", and the actions it requests
are carried out on the run. The audit found the protocol's execution
contract implemented by nothing (`AUDIT.27`). Looking at every way
something is done to a greenhouse today, there are nine, in five shapes:

| Way | Type | Validated in | Timed | Result reported | Run identity |
| --- | --- | --- | --- | --- | --- |
| Watering, harvest, lowering, inspection | `greenhouse_protocol.action.RequestedAction` | `greenhouse_sim/greenhouse_sim/actions/validation.py` | the engine's day, at once, in order (`SimulationEngine.apply_actions`) | an `ActionResult` each, and an `Event` for each carried out | the engine's path: no run id |
| The protocol's execution contract | `ActionExecutionAdapter`, `ActionOutcome`, `ExecutionStatus`, `ActionNotExecutable` | — | — | — | unused |
| The simulator's executor | `greenhouse_sim.executor.ActionExecutor`, `SimulatedOperatorExecutor` | — | — | a world and an `Event` | the engine's path |
| A device's level, a door's or vent's opening | `climate.commands.Command` (`&set=`, `&open=`, `&schedule=`; the viewer's Equipment and Openings) | `greenhouse_sim/greenhouse_sim/services/fields.py` | at a second of the run; at one moment, in the order given | no record: the run's state and the sensors show it | part of it |
| The same every day | `climate.commands.DailyCommand` (`&daily=`, a manifest's) | the same | a time of day, before that moment's other commands | none | part of it |
| A climate target | `climate.commands.TargetChange` (`&targets=`) | `services/fields.py` (`_checked_targets`) | from a moment on, on the minute | none: "targets are not records" (decision 0043) | part of it |
| A target changed while a run plays | `POST /api/scenarios/{id}/playback/targets` | `services/playback.py` | from the clock's next minute | `PlaybackState.targets` | kept, with its epoch (decision 0043) |
| The plant lab's work | `services.plants.LabAction` (`&act=`), as the organ model's `PlantAction` (`biology/tomato/organ/topology.py`) | `services/plants.py` and `biology/tomato/organ/actions.py` | the start of a day | an event in the plant's history, done or not | the lab's run |
| A scenario's crop work | `core.crop.CropWork`: a harvest round and a lowering round every so many days | the manifest's schema | the start of every n-th day | `HARVEST` events to a consumer (`services/crop_log.py`) | part of it |

Starting, pausing, pacing and restarting a run are not done to the
greenhouse, and neither is moving its equipment, which edits the
installation the run is of (#295). They stay outside this decision.

Acting on a greenhouse is to be a core part of the project: people,
control policies and agents trained to control it will act through it, on
a simulated greenhouse and on a physical installation alike, and an action
may be carried out by the simulator, a climate computer, a robot or a
person. Some actions are due at an hour, as commands and target changes
are today; others are to be done in an order, or side by side, as soon as
can be, or within a while. Being late matters, and for some actions being
late is failing: a robot picking a moving target that has passed has
missed it. And who may do what is to be checked by design, in one place.

## Decision

**One action format, in the protocol.** An action says what is to be done,
to what: a kind, its targets by identifier and its parameters, one
discriminated union (`kind`). The kinds are those above under one name
each: a device's level, a target's value, watering, harvesting (the ripe
fruit, a fruit, a truss), lowering, removing a leaf, inspecting. A new
kind is added to the union. No other type of action, one that is
proposed, planned or reported, exists in the protocol, the simulator, its
API or its viewer. A model's own operations inside a rung, such as the
organ crop's, are not actions: nothing proposes or plans them, and they
report no outcome.

**A plan carries actions out.** A plan is a set of planned actions, each an
action with its identifier, its timing, what it waits for, what to do if it
is late, and who proposed it:

- **its timing:** at an instant; in a window, no earlier and no later than
  two instants; or as soon as it can. Any instant: the format bakes in no
  resolution. A planned action may recur (every day at a time, every n
  days), as daily commands and crop work do today;
- **what it waits for:** the planned actions that must be done first. The
  plan is a directed graph without cycles: actions with no order between
  them may be carried out side by side;
- **if it is late:** a tolerance, and what to do past it: carry it out
  late, skip it, carry out a fallback action instead, as a planned action
  of its own with its own outcome, or abort the rest of the plan. A
  critical action is skipped when late and its dependents are cancelled;
- **who may carry it out,** by kind or by identity;
- **who proposed it:** a principal, a person, a policy, a scenario's own
  schedule, by identity.

At one instant, actions are carried out in a fixed order, across every
plan the run has: recurring ones first, then by the order in which the
gateway accepted the revisions that gave them, then by their place in it,
as commands at one moment are today, so that a simulated run under its
plans is deterministic. A recurring action has one anchor, its timing,
moved by its period for each occurrence. Actions are named by the
protocol's own identifiers; an occurrence or a fallback by its action's
and its place.

**A plan belongs to a run, and a run is the protocol's.** A run is what
the consumer interface already names (decision 0040): a run id, its epoch
and its clock. A simulated run is one, as today. A physical installation
serves one too: one run for each configuration of its equipment, so that
changed equipment makes a new run, as it does for a simulated one; its
epoch rising each time its gateway starts again; its clock the wall
clock. A run that has finished, and a recorded one, cannot be acted on
(`ActionNotExecutable`).

**A gateway carries the plan; executors carry out actions.** Each run has a
gateway, its local endpoint, which:

- holds the run's plan and its revisions, and schedules its actions;
- applies the lateness rules, since it alone knows what was due when;
- authorises (below);
- writes the outcome log;
- serves the run's read side, the consumer interface's observations,
  events and outcomes, and its write side, plans given, revised and
  cancelled.

Behind it, an executor only carries out one action it is assigned, at an
instant, and reports when it started and finished, and whether it was
done, failed or refused because the greenhouse was not as the action
needed. It says which kinds it carries out, which instants it can honour
for each, how many actions it can carry out at once, and how long each
may take. An assignment is carried out at most once, even if it is sent
again; one revoked before it started is not carried out; and one whose
report never comes is resolved as unconfirmed, not waited for. The simulated run
is an executor; so are a climate computer, a robot and a person with a
task list. The protocol has the two contracts, one for a gateway and one
for an executor; its execution contract becomes the second.

**Checks happen at two moments.** When a plan is given, the gateway
refuses a malformed one whole, by its receipt, writing no outcome; and
refuses, as outcomes recorded then, each well-formed action its principal
may not carry out, of a kind no executor carries out, on a device, plant
or target the run does not have, or at an instant no executor can honour;
a window or an as-soon-as-possible action starts at the first instant one
can. When an action falls due, the gateway checks its authorisation again,
since rights may have changed, and the executor checks the greenhouse: a
truss to cut that has not grown is refused then, not when the plan was
given.

**Authorisation by design, in the gateway alone.** Every action carries its
principal, and that principal is the plan's authenticated submitter
unless the submitter is granted to propose on its behalf; a plan's
revisions and cancellations are its owner's. Authorisation groups grant
action kinds to principals, optionally limited to targets: devices,
plants, a controller's targets. The gateway is the one place they are
enforced; a refusal is an outcome, with its reason. The groups'
configuration is versioned, and an input of the run: the version a
simulated run starts with is part of its request, and each change takes
effect from an instant and is recorded, so a replay decides the same. Executors and sensors hold no rights: they trust the
gateway's channel, which must be authenticated. Who defines the groups is
the deployment's: a platform may manage them and hand them to its
gateway. The simulator's gateway has one group, the local operator,
allowed everything, so the mechanism exists from the start.

**One outcome record.** Each planned action ends in one outcome: carried
out, carried out late, missed, refused (and why), failed, cancelled,
superseded by a later revision, or unconfirmed when its executor never
reported. It carries its action as it was asked, and names its plan and
principal;
when the action was due, when it started and finished, and when its
outcome was decided, which every outcome has and which orders the log; its
executor, by kind and identity; and its effect, typed by the action's
kind. Outcomes are records of their own, in a log of their own with the
consumer interface's cursor rules. A carried-out action's effect is still
the event it produced (a harvest stays a `HARVEST` event, naming its
action). A control policy and a training loop read outcomes and
observations; neither reads anything else.

**A revision steers from then on: the gateway's rule.** A revision given to
a run's gateway replaces, from the next instant its executors can honour,
the actions not yet started; what was started or done keeps its outcome.
For a simulated run this is decision 0043 for every kind: the same run id
and epoch, records before the change unchanged, the clock waiting until
the rest of the day is worked out again. For a physical run the clock is
the wall clock, and from then on is from now. A plan given before a
simulated run starts is part of the run's request and identity, as
commands and target changes are today.

**Simulated run identities stay.** A plan made only of what today's
schedule can say, levels and openings at instants, daily commands, target
changes and a scenario's crop work, has the identity the run has today, so
no run id, replay digest or kept opening day changes. A plan that says
more is another run.

**Acting is an interface of its own.** The consumer interface stays
read-only, its routes `GET` (decision 0040), and what it reaches stays
observed (decision 0036): giving a plan is the gateway's write side, an
actuation contract of its own in the protocol.

## Consequences

- `RequestedAction`, `ActionResult`, the engine's `apply_actions`, the
  simulator's `ActionExecutor`, the lab's `LabAction`, the separate
  `Command`, `DailyCommand` and `TargetChange` types, `CropWork` and the
  playback's targets route are folded into the one format and then
  removed, step by step ([P13](../roadmap/p13-actions.md)). The address's
  `&set=`, `&schedule=`, `&daily=` and `&targets=` stay as short spellings
  of a plan, read into it.
- The simulator ships a gateway, in process: its playback, which owns its
  run's plan, outcome log and one authorisation group, with the simulated
  run as its executor. A physical site runs a gateway of its own with real
  executors behind it, through the same two contracts.
- Today's simulated executor carries out crop work at a day's start only,
  where the organ crop steps, and so refuses a crop action due at any
  other instant when the plan is given. The format does not change when it
  learns to: crop work within the day is a project of its own, recorded on
  the roadmap.
- Decision 0043's "targets are not records" no longer holds once outcomes
  are records: a target changed is an outcome a consumer reads. Its
  steering holds for every kind, as the gateway's rule.
- P11's actuation interface, which P10 left out, is this one.
- The protocol's version moves (a minor version, below 1.0) with the
  first step that changes it, which keeps the old names as deprecated
  aliases and says in the changelog what each became; the step that
  removes them moves it again.
- The run's organ crop has no water in its root zone: its plants' water
  status is always full. The run refuses `water` until a rung of the crop
  models it, rather than report a watering that changes nothing.
- An executor with durations and limited hands, a simulated robot, is
  needed for lateness to arise in the simulator at all: its operator
  carries actions out at once.
- How a gateway and its executors and sensors authenticate each other is
  a requirement here, not a design: the transport is a deployment's.
- Worth revisiting if a kind needs timing the plan cannot express, if
  outcomes and events turn out to say the same thing twice, or if one
  enforcement point proves too coarse for a deployment.
