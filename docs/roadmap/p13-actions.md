# P13: One action format, and a plan that carries it out

**Status:** proposed, with decision 0046 ([below](#open-questions) are the
questions it leaves open). Part of the [simulator roadmap](README.md).

## Goal

Whoever acts on a greenhouse, a person in the viewer, a control policy, an
agent being trained, a scenario's own schedule, does so in one format, and
whatever carries the action out, the simulator's run today, a person, a
robot or a climate computer later, reports what became of it in one
record. Some actions are due at an hour; others wait for one another, run
side by side as soon as they can, or within a while; each says what to do
if it is late, and a critical one that is late is missed rather than done
at the wrong moment.

Today there are nine ways of acting in five shapes, and the protocol's own
execution contract is used by none of them (`AUDIT.27`); decision 0046
lists them. This project folds them into one, and removes the rest.

## Dependencies

- P10, the consumer interface (decision 0040), whose cursor rules the
  outcome log keeps, and decision 0036: what a consumer reads stays
  observed.
- P11 and decisions 0042 and 0043: the climate controller, its targets, a
  command taking a device out of a loop's hands, and steering a playing run
  from then on, in the same run and epoch.
- Decision 0035: one simulator, the run; the engine's actions move to it.
- Decision 0041: the playback, its one clock and its epochs.
- The audit's `Simulator` object (`AUDIT.15`), which owns the runs and so
  their plans, before the API takes plans (P13.5).
- The installation editor (P12, #295) is not a dependency: moving equipment
  edits the installation, which is not an action.

## Design

### The action

One discriminated union in the protocol, `Action`, by `kind`. Sketched as
fields:

| Kind | Fields | Today |
| --- | --- | --- |
| `set_level` | `device_id`, `level`: 0 to 1, or `auto` to hand the device back to its control loop | `Command`, `DailyCommand`, `&set=`, `&open=`, `&schedule=`, `&daily=`: equipment and openings |
| `set_target` | `target` (a controller's target: `heating_day`, `heating_night`, more with P11), `value`, `unit` | `TargetChange`, `&targets=`, the playback's targets route |
| `water` | `plant_id`, `amount_ml`, at most `MAX_WATER_AMOUNT_ML` | `WaterPlantAction` |
| `harvest` | `plant_id`, `scope`: `ripe` (every ripe fruit), `fruit` or `truss`, with its organ's id | `HarvestPlantAction`, the lab's `harvest_fruit` and `harvest_truss`, crop work's harvest round |
| `lower` | `plant_id`, one of `by_cm`, `by_internodes`, `to_head_room_m` | `LowerPlantAction`, the lab's `lower_stem`, crop work's lowering round |
| `remove_leaf` | `plant_id`, `leaf_id` | the lab's `remove_leaf` |
| `inspect` | `plant_id`, `reason` | `ScheduleInspectionAction` |

`auto` is new: today a command takes a device out of its loops' hands for
the rest of the run (decision 0042, P11), and nothing gives it back.

An action names no time and no executor: those belong to the plan.

### The plan

```
PlannedAction
  action_id: ItemId                 unique in its plan
  action: Action
  timing: At(at) | Window(not_before, not_after) | Asap(deadline: optional)
  every: Recurrence(period, from, until: optional) | None
  after: tuple[ItemId, ...]         planned actions that must be done first
  if_prerequisite_fails: cancel | proceed          cancel by default
  lateness: Lateness
  expected_duration_s: optional     what the planner expects; the executor reports what it took
  executed_by: tuple[ExecutorKind, ...] | None     who may carry it out; anyone if None
  proposed_by: Proposer             a person, a policy, a schedule, a scenario; with an id

Lateness
  tolerance_s: 0                    how late still counts as on time
  on_late: run_late | skip | fallback | abort_plan     run_late by default
  fallback: Action | None           carried out instead, when on_late is fallback
  critical: false                   skip when late, cancel what waits for it

Plan
  plan_id, greenhouse_id, revision: int
  actions: tuple[PlannedAction, ...]
```

- **Timing.** `At` is due at its instant. `Window` may start at any
  admissible instant between its two. `Asap` starts at the first
  admissible instant after what it waits for is done, before its deadline
  if it has one. An executor says which instants are admissible for each
  kind: today's run takes a level at any second, a target on the minute
  (`TARGET_EVERY_S`) and crop work at a day's start. An `At` at an instant
  that is not admissible is refused, as a target off the minute is today;
  a `Window` or an `Asap` starts at the next admissible one.
- **Recurrence** expands to one planned action per occurrence, each with
  its own id (`{action_id}@{n}`) and its own outcome, as
  `DailyCommand.through` expands today.
- **The graph.** `after` makes the plan a directed graph without cycles,
  checked when a plan is given, with its ids unique and every prerequisite
  in it. Actions with no path between them may run side by side.
- **One order at one instant.** Recurring actions first (as daily commands
  come first today), then by revision, then by place in the plan. A later
  `set_level` to one device at one instant wins, as a later command does.
- **Revisions.** A plan given again with its `plan_id` and a higher
  revision replaces, from an instant on, the actions not yet started: one
  dropped is superseded, one started or done keeps its outcome. This is
  how a playing run is steered (below).

### Lateness

An action is late when it cannot start by its due instant plus its
tolerance: its `At` has passed, its window has closed, its deadline has
gone, or what it waits for finished too late. Then:

| `on_late` | What the executor does | Its outcome | What waits for it |
| --- | --- | --- | --- |
| `run_late` | carries it out as soon as it can | `late`, with the delay | waits, then goes on |
| `skip` | nothing | `missed` | as `if_prerequisite_fails` says |
| `fallback` | carries out the fallback action instead | `missed`, naming the fallback's outcome | as `if_prerequisite_fails` says |
| `abort_plan` | nothing, and starts nothing else of the plan | `missed` | every action not started: `cancelled` |

`critical` is `skip` with every action that waits for it cancelled. A robot
to pick a fruit on a moving line within two seconds of its pass is
`At(pass)`, tolerance 2 s, critical: past that it is missed, and the
placing that waits for it is cancelled rather than done on nothing.

Today's run carries every action out at once, so it is late only when a
plan's instant has already passed as it is given. Durations and limited
hands come with a simulated executor that has them (P13.4), so that
lateness can be exercised before any real executor exists.

### The outcome

```
ActionOutcome                       a record, frozen
  outcome_id, greenhouse_id, plan_id, revision, action_id
  status: executed | late | missed | refused | failed | cancelled | superseded
  due: Instant | Window             when it was due
  started_at, finished_at: Instant | None
  executor: ExecutorKind | None     who carried it out
  reason: str | None                why it was refused, failed, missed or cancelled
  effect: dict                      what it did: the harvested mass, the level set
  event_id: str | None              the event it produced, if any
```

Every planned action, and every occurrence of a recurring one, ends in
exactly one outcome. Outcomes are a third log beside observations and
events, with the consumer interface's rules: delivery order, dense
cursors, nothing delivered after the clock, an epoch never going back. An
executed harvest still produces its `HARVEST` event, which names its
action, so a consumer reading events today reads the same events.
`refused` replaces `ActionResult`: a check before carrying out is an
outcome too.

### The executor

The protocol's `contracts/execution.py` becomes the one contract:

```
ActionExecutor (Protocol)
  kinds() -> frozenset[str]               the kinds it carries out
  admissible(kind, instant) -> bool       the instants a kind may start at
  submit(plan, *, from_: Instant) -> Receipt
      the plan, or its next revision, in force from `from_`; the actions it
      cannot take are refused at once, as outcomes, with the reason
  cancel(plan_id, action_ids | None, *, from_: Instant) -> Receipt
  plan(plan_id) -> PlanState              each action: waiting, due, started, or its outcome
  raises ActionNotExecutable              a recorded history, which cannot be acted on
```

Outcomes are not returned by `submit`: they are written as the clock
passes, and read from the log, by a consumer or by a training loop alike.

### The run as the executor

- **Before the run:** the plan is part of the run's request
  (`RunRequest`), beside its scenario, layout and weather, and part of its
  identity: the same plan, the same run.
- **Identities stay.** A plan made only of what today's schedule says, a
  device's levels and openings at instants, daily commands, target changes
  and the manifest's crop work, is identified as today's schedule is, so
  every run id, replay digest, kept opening day and reference view stays.
  The manifest's `crop_work` and daily commands stay its spelling of a
  standing plan until the reference run is next written again (P11.5).
- **While it plays:** a revision is steering, decision 0043 for every kind.
  It takes effect from the clock's next admissible instant, in the same
  run id and epoch; records before it stand; the clock waits until the
  rest of the day is worked out again under it. A restart is a new epoch of
  the run's own plan, without the revisions.
- **Checkpoints** keep the plan in force and the outcomes so far, in a new
  checkpoint format; format 3, with commands and target changes, is read
  as a plan of them.
- **The organ crop** takes `harvest`, `lower` and `remove_leaf` at a day's
  start, through its own `PlantAction`, which stays the crop model's inner
  step; the plant lab gives the same actions.
- **The controller** keeps its loops (P11). `set_target` changes their
  targets; `set_level` takes a device out of their hands, and `auto` gives
  it back.

### A policy, and a training loop

A policy does what a person in the viewer does, in the same format: it
reads observations and outcomes up to the clock, gives a revision of its
plan, and the clock moves on. In a simulation the loop also moves the
clock:

```
observe(up_to=t) -> observations, outcomes
plan = policy(observations, outcomes)
executor.submit(plan, from_=t)
run.advance(until=t + step)
```

Nothing in it is particular to training: a dashboard proposing a plan to a
grower, and an agent learning one, give the same plans and read the same
outcomes. The engine's day interface (`examples/03_close_the_loop.py`)
becomes this loop on the run.

### Acting through the API

The consumer interface stays read-only, its routes `GET` (decision 0040),
and what it reaches observed (decision 0036). Acting is an
actuation contract of its own in the protocol (`contracts/actuation.py`),
with its routes, `POST` a plan or a revision to a run, `GET` the plan in
force, and the outcome log is read, as every log is, through the consumer
interface. The local API has no users (decision 0009); who may act on a
run when the interface leaves the machine is a question below.

### What becomes of today's paths

| Today | Becomes | Removed in |
| --- | --- | --- |
| `RequestedAction` and its four types, `ActionResult` | `Action`; a refusal is a `refused` outcome | P13.7 |
| `ActionExecutionAdapter`, `ActionOutcome`, `ExecutionStatus` | the executor contract and the outcome record above | P13.1 |
| `greenhouse_sim.executor` (`ActionExecutor`, `SimulatedOperatorExecutor`, `executor_for`), `SimulationEngine.apply_actions` | the run as the executor; the simulated operator its first kind of executor | P13.7 |
| `Command`, `&set=`, `&open=`, `&schedule=` | `set_level` at an instant | the types in P13.2; the spellings stay |
| `DailyCommand`, `&daily=` | `set_level` every day at a time | P13.2 |
| `TargetChange`, `&targets=` | `set_target` at an instant, on the minute | P13.2 |
| `POST /api/scenarios/{id}/playback/targets` | a plan revision given to the playing run | P13.5, an alias for one release |
| `LabAction`, `&act=` | `harvest`, `lower`, `remove_leaf` at a day's start | P13.3 |
| `CropWork` | a standing plan's recurring `harvest` (`ripe`) and `lower` (`to_head_room_m`) on every plant | P13.3; its manifest spelling with P11.5 |

## Steps

| Step | What | Commit title | Status |
| --- | --- | --- | --- |
| P13.1 | The format: `Action`, `PlannedAction`, `Plan`, `ActionOutcome`, the executor contract and `ActionNotExecutable`, with checks (ids, the graph, windows, one outcome per action) as conformance functions and their tests; the published JSON Schemas. Decision 0046 accepted. | `feat(protocol): one action, plan and outcome format` | Proposed |
| P13.2 | The run carries out a plan of today's kinds: levels, openings, daily commands and targets become a plan internally; `RunRequest` holds it; the address's spellings are read into it. Every run id, replay digest and kept opening day unchanged. Checkpoints in a new format, format 3 read. | `refactor(sim): the run carries out its schedule as a plan` | Proposed |
| P13.3 | Crop actions on the run: `harvest`, `lower`, `remove_leaf`, `water`, `inspect` at a day's start; the plant lab and crop work give them; events name their actions; the outcome log, served to consumers. | `feat(sim): crop actions and their outcomes on the run` | Proposed |
| P13.4 | The graph, windows and lateness on the run, with a simulated executor whose actions take time and share hands, so that `late`, `missed`, fallbacks and cancelled dependents happen, deterministically. | `feat(sim): plans with order, windows and lateness` | Proposed |
| P13.5 | The actuation contract and its routes: give a plan before a run, steer a playing one, read the plan in force; the playback's targets route becomes an alias. | `feat(api): give, steer and read a run's plan` | Proposed |
| P13.6 | The viewer: the Equipment, Openings and Targets panels and the plant lab write one plan; a plan lane in the timeline shows what was due, what happened and why. | `feat(viewer): one plan, and its outcomes in the timeline` | Proposed |
| P13.7 | The old paths removed: the engine's actions, `greenhouse_sim.executor`, `RequestedAction`, `ActionResult`, `LabAction`; the close-the-loop example as a policy loop on the run; the protocol's minor version and the changelog. | `refactor: one way to act on a greenhouse` | Proposed |
| P13.8 | The QA scenario below, run and recorded. | `test(e2e): a plan carried out, late and on time` | Proposed |

## Acceptance criteria

- [ ] The protocol has one action type, one plan, one outcome record and
  one executor contract, each with conformance checks and a published
  schema.
- [ ] Every way of acting in decision 0046's table goes through them, and
  none of the old types or routes is left (a test lists the names that
  may not come back).
- [ ] A plan of today's kinds gives today's run: every run id, replay
  digest, kept opening day and reference view unchanged.
- [ ] The same plan gives the same records and outcomes, run after run;
  simultaneous actions in the documented order.
- [ ] Each lateness policy gives the documented outcomes, its dependents
  included, on the simulated executor with durations.
- [ ] Every planned action ends in exactly one outcome, and the outcome log
  keeps the consumer interface's rules (`check_polls`).
- [ ] A revision steers a playing run from the clock's next admissible
  instant, in the same run and epoch, for every kind.
- [ ] A recorded history refuses a plan with `ActionNotExecutable`.
- [ ] A control policy runs on the run through the loop above.

## Final QA scenario

On the reference greenhouse, its run played back, in the viewer and with a
consumer following:

1. Give a plan: the day's heating target to 22 °C at 08:00; harvest truss
   3 of plant 30, then lower plant 30, as soon as possible; open roof vent
   1 between 11:00 and 11:30.
2. The timeline's plan lane shows each due, then done, with its outcome;
   the consumer reads the same outcomes, and the harvest's event names its
   action.
3. Give, at 10:05, a critical action due at 10:00 with no tolerance, and
   one that waits for it: the first is missed, the second cancelled, with
   their reasons.
4. Steer the playing run: a revision drops the vent's window before it
   opens. It is superseded; the run id and epoch stay; nothing delivered
   before changes.
5. Restart: a new epoch of the run's own plan, without the revisions.
6. A plan of today's commands and targets alone: the run id is today's.

## Open questions

1. **Time.** Each kind's admissible instants as today (a second for a
   level, the minute for a target, a day's start for crop work), or crop
   actions within a day, which the organ crop would then have to step
   through?
2. **Whose plan.** A plan given to one run and its epochs, with a
   scenario's standing plan (daily commands, crop work) under it, as
   proposed; or plans that belong to an installation and outlive its runs?
3. **Who may act.** When the actuation interface leaves the machine: the
   proposer recorded and nothing refused, or rights by kind and by
   executor, refused as outcomes?
4. **Outcomes or events.** Outcomes as a log of their own, as proposed,
   or as events of a new type in the events log, which consumers already
   read?
5. **Lateness in the simulator.** A simulated executor with durations and
   limited hands (P13.4), as proposed, or lateness only from plans given
   too late, until a real executor exists?
