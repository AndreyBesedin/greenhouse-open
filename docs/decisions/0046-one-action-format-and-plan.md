# 0046: One action format, and a plan that carries it out

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
control policies and agents trained to control it will act through it, and
an executor may be a person, a robot or a climate computer, as well as the
simulator. Some actions are due at an hour, as commands and target changes
are today; others are to be done in an order, or side by side, as soon as
can be, or within a while. Being late matters, and for some actions being
late is failing: a robot picking a moving target that has passed has
missed it.

## Decision

**One action format, in the protocol.** An action says what is to be done,
to what: a kind, its targets by identifier and its parameters, one
discriminated union (`kind`). The kinds are those above under one name
each: a device's level, a target's value, watering, harvesting (the ripe
fruit, a fruit, a truss), lowering, removing a leaf, inspecting. A new
kind is added to the union; no other action type exists, in the protocol,
the simulator, its API or its viewer.

**A plan carries actions out.** A plan is a set of planned actions, each an
action with its identifier, its timing, what it waits for and what to do
if it is late:

- **its timing:** at an instant; in a window, no earlier and no later than
  two instants; or as soon as it can. A planned action may recur (every
  day at a time, every n days), as daily commands and crop work do today;
- **what it waits for:** the planned actions that must be done first. The
  plan is a directed graph without cycles: actions with no order between
  them may be carried out side by side;
- **if it is late:** a tolerance, and what to do past it: carry it out
  late, skip it, carry out a fallback action instead, or abort the rest of
  the plan. A critical action is skipped when late and its dependents are
  cancelled;
- **who may carry it out,** and who proposed it: a person, a policy, a
  scenario's own schedule.

At one instant, actions are carried out in a fixed order: recurring ones
first, then by the plan revision that gave them and their place in it, as
commands at one moment are today, so that a run under a plan is
deterministic.

**One outcome record.** Each planned action ends in one outcome: carried
out, carried out late, missed, refused (and why), failed, cancelled, or
superseded by a later revision. It names its action and plan, when the
action was due and when it started and finished, its executor and its
effect. Outcomes are records of their own, in a log of their own with the
consumer interface's cursor rules. A carried-out action's effect is still
the event it produced (a harvest stays a `HARVEST` event, naming its
action). A control policy and a training loop read outcomes and
observations; neither reads anything else.

**One executor contract.** The protocol's execution contract becomes the
only one: an executor says which kinds it carries out, takes a plan or a
revision of one from an instant on, refuses what it cannot do as refused
outcomes, and writes outcomes as time passes. A recorded history raises
`ActionNotExecutable`. The simulator's run implements it, replacing the
engine's executor (decision 0035).

**A revision steers from then on.** A plan given before a run starts is
part of the run's request and identity, as commands and target changes are
today. A revision given while the run plays replaces the actions not yet
started from the clock's next admissible instant, in the same run and
epoch, as decision 0043 has it for targets; what was carried out before
stands.

**Run identities stay.** A plan made only of what today's schedule can say,
levels and openings at instants, daily commands, target changes and a
scenario's crop work, has the identity the run has today, so no run id,
replay digest or kept opening day changes. A plan that says more is
another run.

**Acting is an interface of its own.** The consumer interface stays
read-only, its routes `GET` (decision 0040), and what it reaches stays
observed (decision 0036): submitting a plan is a separate actuation
contract in the protocol, with its own routes and rights.

## Consequences

- `RequestedAction`, `ActionResult`, the engine's `apply_actions`, the
  simulator's `ActionExecutor`, the lab's `LabAction`, the separate
  `Command`, `DailyCommand` and `TargetChange` types, `CropWork` and the
  playback's targets route are folded into the one format and then
  removed, step by step ([P13](../roadmap/p13-actions.md)). The address's
  `&set=`, `&schedule=`, `&daily=` and `&targets=` stay as short spellings
  of a plan, read into it.
- Decision 0043's "targets are not records" no longer holds once outcomes
  are records: a target changed is an outcome a consumer reads. Its
  steering, from then on in the same run and epoch, holds for every kind.
- P11's actuation interface, which P10 left out, is this one.
- The protocol's version moves (a minor version, below 1.0), and its
  changelog says what each old name became.
- An executor with durations and limited hands, such as a simulated robot,
  is needed for lateness to arise in the simulator at all: its operator
  carries actions out at once.
- Worth revisiting if a kind needs timing the plan cannot express, or if
  outcomes and events turn out to say the same thing twice.
