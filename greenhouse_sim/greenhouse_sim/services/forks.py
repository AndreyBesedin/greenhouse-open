"""A fork: a run acted on from a past instant (P17.8, decision 0065).

A position in the past changes nothing: to act from a moment of an epoch, a
person or a program forks it. A fork is a new epoch, with its parent, the exact
instant, the state it inherits (the parent's checkpoint, and its trajectory
digest through it), the changes it inherits and the inputs it changes from then
on. It does not compute what lies before that checkpoint, and the epoch it came
from stays in the store, served as it was.

What it is made of is written before its manifest, so that a fork cut short is
never listed:

- **its state:** the nearest checkpoint at or before the instant, a copy of its
  own, so that it can be carried on and read when its parent has been deleted;
- **its log:** the entries given by the instant, renamed to its own run and
  epoch, then the changes it is asked to make there. A worker takes it up as it
  takes up an epoch to be carried on (`workers.resume`): the checkpoint
  restored, and the log applied again;
- **its parent's outcomes,** which say what crop actions before its checkpoint
  did: they are not worked out again here either.

A rearranged layout is a fork too (#271, decision 0049), of the run of that
layout, whose `run_id` differs. A run has one layout from its start, so a layout
acts from the checkpoint and not from a moment inside a day, and the fork says
that instant. A layout whose crop is not the checkpoint's is refused: the state
cannot be inherited, and a new run of that layout is what is meant.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from pydantic import JsonValue, TypeAdapter

from greenhouse_sim.climate.commands import TARGET_EVERY_S
from greenhouse_sim.services import scenario_files
from greenhouse_sim.services.checkpoints import upload_checkpoint
from greenhouse_sim.services.climate_runs import run_schedule
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, read_as
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.interventions import (
    LOGGED,
    ActionsCancelled,
    Asked,
    LevelsAsked,
    Logged,
    PlanCancelled,
    PlanGiven,
    TargetsAsked,
    TargetsChanged,
    check_allowed,
    levels_plan,
    spelled,
)
from greenhouse_sim.services.playback import FIRST_EPOCH
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    ForkOf,
    LogEntry,
    ObjectStore,
    compress,
    decompress,
    digest_of,
    started_epochs,
)
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.scenarios import layout_name
from greenhouse_sim.services.sensors import run_start

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

_CHANGES: Final = TypeAdapter[tuple[Asked, ...]](tuple[Asked, ...])


def fork(
    simulator: Simulator,
    objects: ObjectStore,
    run_id: str,
    epoch: int,
    at_s: float,
    *,
    layout: str | None = None,
    changes: Sequence[Asked] = (),
    seconds_per_day: float | None = None,
) -> EpochStore:
    """A new epoch, `queued`, forked from `epoch` of `run_id` at `at_s`, in its
    `layout` from then on if given, with `changes` given at that moment, and
    what a worker needs to run it (`scenario_files.carry`).
    Refused if the parent does not hold that moment, or the run ends there.
    Whoever starts epochs of one store does it one at a time, so that two are
    never given a number."""
    if epoch not in stored_epochs(objects, run_id):
        raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
    parent = EpochStore(objects, run_id, epoch)
    manifest = parent.manifest()
    if not parent.start_s() <= at_s <= parent.frontier_s():
        raise InvalidRequest(
            f"a fork of epoch {epoch} of {run_id} branches between {parent.start_s():.15g} and "
            f"{parent.frontier_s():.15g} s, what it holds, not at {at_s:.15g} s"
        )
    if manifest.duration_s is not None and at_s >= manifest.duration_s:
        raise Conflict(f"the run ends at {at_s:.15g} s: there is nothing to fork from there")
    for change in changes:
        check_allowed(simulator, change)
    chosen = layout_name(layout or manifest.layout)
    moved = chosen != manifest.layout
    request = RunRequest(manifest.scenario_id, layout=chosen, seed=manifest.seed)
    _, new_run = air_through_a_run(simulator, request)
    inherited = parent.inherited_at(at_s)
    branch_s = inherited.start_s if moved else at_s
    state = None if inherited.checkpoint is None else _state(inherited.checkpoint, chosen)
    if state is not None:
        # Refused as an upload is, if its crop is not the layout's.
        upload_checkpoint(simulator, json.loads(decompress(state)))
    started = started_epochs(objects, new_run)
    number = started[-1] + 1 if started else FIRST_EPOCH
    made = EpochStore(objects, new_run, number)
    entries = _inherited_log(parent, branch_s, new_run, number)
    logged = [
        *entries,
        *_changes_at(
            simulator,
            request,
            changes,
            run_id=new_run,
            number=number,
            at_s=branch_s,
            first=len(entries),
        ),
    ]
    scenario_file = scenario_files.carry(simulator.catalogue, objects, manifest.scenario_id)
    made.write_fork(
        EpochManifest(
            run_id=new_run,
            epoch=number,
            scenario_id=manifest.scenario_id,
            seed=manifest.seed,
            layout=chosen,
            duration_s=manifest.duration_s,
            created_at=datetime.now(UTC),
            fork=ForkOf(
                run_id=run_id,
                epoch=epoch,
                at_s=branch_s,
                start_s=inherited.start_s,
                digest=inherited.digest,
                checkpoint_sha256=None if state is None else digest_of(state),
                inherited=len(entries),
                layout=chosen if moved else None,
            ),
            scenario_file=scenario_file,
            seconds_per_day=seconds_per_day,
        ),
        state=state,
        log=logged,
        outcomes=parent.outcomes_kept(),
    )
    return made


def _state(checkpoint: bytes, layout: str) -> bytes:
    """A parent's checkpoint as a fork inherits it, of the layout it goes on in."""
    document = json.loads(decompress(checkpoint))
    if document.get("layout") == layout:
        return checkpoint
    return compress(json.dumps(document | {"layout": layout}))


def _inherited_log(parent: EpochStore, at_s: float, run_id: str, number: int) -> list[LogEntry]:
    """The entries of a parent's log given by `at_s`, each named for the run and
    epoch that now holds it, and numbered there. One that named another's was
    refused as stale when it was given, did nothing, and is left behind: renamed
    or not, it could be accepted here."""
    found: list[LogEntry] = []
    for entry in parent.logged():
        if entry.given_s > at_s:
            continue
        what = _renamed(entry.what, parent, run_id, number)
        if what is not None:
            found.append(
                entry.model_copy(update={"seq": len(found), "request": None, "what": what})
            )
    return found


def _renamed(
    what: dict[str, JsonValue], parent: EpochStore, run_id: str, number: int
) -> dict[str, JsonValue] | None:
    """What an entry says, as the fork gives it, if it was the parent's to give."""
    was = parent.epoch
    change: Logged = LOGGED.validate_python(what)
    match change:
        case PlanGiven(plan=plan):
            if (plan.run_id, plan.epoch) != (parent.run_id, was):
                return None
            change = PlanGiven(plan=plan.model_copy(update={"run_id": run_id, "epoch": number}))
        case ActionsCancelled(keys=keys):
            kept = tuple(k.model_copy(update={"epoch": number}) for k in keys if k.epoch == was)
            if not kept:
                return None
            change = ActionsCancelled(keys=kept)
        case PlanCancelled(epoch=epoch):
            if epoch != was:
                return None
            change = change.model_copy(update={"epoch": number})
        case TargetsChanged():
            pass
    return change.model_dump(mode="json")


def _changes_at(
    simulator: Simulator,
    request: RunRequest,
    changes: Sequence[Asked],
    *,
    run_id: str,
    number: int,
    at_s: float,
    first: int,
) -> list[LogEntry]:
    """What a fork is asked to change, as entries of its log given at its
    instant. A target refused refuses the fork, as it refuses a run."""
    start = run_start(simulator.catalogue, request.scenario_id)
    found = []
    for seq, change in enumerate(changes, first):
        effect_s = at_s
        match change:
            case TargetsAsked(targets=targets):
                effect_s = (at_s // TARGET_EVERY_S + 1) * TARGET_EVERY_S
                moved = tuple((effect_s, name, value) for name, value in targets.items())
                # Refused, as a run's target changes are, whatever comes after.
                run_schedule(
                    simulator.catalogue, _with_plan(request, RunPlan.requested(targets=moved))
                )
                logged: Logged = TargetsChanged(changes=moved)
            case LevelsAsked(levels=levels):
                logged = PlanGiven(
                    plan=levels_plan(
                        levels,
                        run_id=run_id,
                        epoch=number,
                        start=start,
                        at_s=at_s,
                        plan_id=f"fork_levels_{seq}",
                    )
                )
            case PlanGiven(plan=plan):
                logged = PlanGiven(plan=plan.model_copy(update={"run_id": run_id, "epoch": number}))
            case ActionsCancelled() | PlanCancelled():
                raise InvalidRequest("a fork is given what to do, not what to cancel")
        found.append(
            LogEntry(
                seq=seq,
                at_s=effect_s,
                given_s=at_s,
                by=spelled(LOCAL_OPERATOR),
                what=logged.model_dump(mode="json"),
            )
        )
    return found


def asked(body: bytes) -> tuple[Asked, ...]:
    """The changes a fork is asked to make, as a request's body lists them: none,
    if it has none."""
    if not body.strip():
        return ()
    return read_as("a list of changes", lambda: _CHANGES.validate_json(body))


def _with_plan(request: RunRequest, plan: RunPlan) -> RunRequest:
    return RunRequest(request.scenario_id, layout=request.layout, plan=plan, seed=request.seed)
