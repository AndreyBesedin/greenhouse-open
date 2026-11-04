"""The runs kept in a simulator's run store, as a client lists, opens and
plays them (P17.4, decision 0065): a scenario's stored runs, one epoch of
one, the records it delivered by a moment, and the positions a viewer takes
over an epoch (`stored_playback`). The routes call these and answer with what
they return (decision 0021). A simulator made with no run store keeps none:
every question about its runs is a refusal that says so.
"""

from datetime import timedelta

from greenhouse_protocol.contracts.consumer import EventBatch, ObservationBatch, OutcomeBatch
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome
from pydantic import JsonValue

from greenhouse_sim.services.consumer import batch_cursor, batch_limit
from greenhouse_sim.services.errors import Conflict, NotFound
from greenhouse_sim.services.playback import DEFAULT_SECONDS_PER_DAY
from greenhouse_sim.services.run_store import (
    ObjectStore,
    Status,
    StoredRun,
    stored_run,
    stored_runs,
)
from greenhouse_sim.services.run_store import delete_epoch as delete_stored_epoch
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.stored_playback import Position, PositionState, Records, StoredEpoch


def _objects(simulator: Simulator) -> ObjectStore:
    if simulator.runs is None:
        raise NotFound("this simulator keeps no runs: it was made with no run store")
    return simulator.runs


def runs_of(simulator: Simulator, scenario_id: str) -> list[StoredRun]:
    """The stored epochs of a scenario's runs, by run and epoch. A scenario
    the simulator does not know is not found."""
    if simulator.catalogue.entry(scenario_id) is None:
        raise NotFound(f"there is no scenario {scenario_id!r}")
    return _pauses_said(simulator, stored_runs(_objects(simulator), scenario_id))


def all_runs(simulator: Simulator) -> list[StoredRun]:
    """Every stored epoch, the newest started first and those with no start
    time last: what a landing page shows of the runs of all scenarios."""
    found = _pauses_said(simulator, stored_runs(_objects(simulator)))
    return sorted(
        found,
        key=lambda run: (
            run.created_at is None,
            -(run.created_at.timestamp() if run.created_at is not None else 0.0),
            run.run_id,
            run.epoch,
        ),
    )


def epoch_of(simulator: Simulator, run_id: str, epoch: int) -> StoredRun:
    """One stored epoch, as the list shows it."""
    objects = _objects(simulator)
    if epoch not in stored_epochs(objects, run_id):
        raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
    return _pauses_said(simulator, [stored_run(objects, run_id, epoch)])[0]


def _pauses_said(simulator: Simulator, runs: list[StoredRun]) -> list[StoredRun]:
    """`runs`, those running that a playback of this simulator holds said to be
    paused: the store calls them running, and they stand still."""
    held = {
        (playback.run_id, epoch)
        for playback in simulator.playbacks.all()
        if (epoch := playback.epoch_held()) is not None
    }
    return [
        run.model_copy(update={"paused": True})
        if run.status == Status.RUNNING and (run.run_id, run.epoch) in held
        else run
        for run in runs
    ]


def delete_epoch(simulator: Simulator, run_id: str, epoch: int) -> dict[str, JsonValue]:
    """Removes a stored epoch a person no longer wants, with the positions
    over it. One the store calls queued or running is not removed, whoever
    works on it: a worker in a process of its own is seen by no playback here.
    Nor is one a replaced producer is still writing, whatever the store says
    yet. A run left running by a producer that is gone stays so until it is
    found interrupted, as a simulator starts or when it is asked to resume or
    stop (`interrupted`, P17.9); one asked to stop, until its worker has looked."""
    objects = _objects(simulator)
    if epoch not in stored_epochs(objects, run_id):
        raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
    if stored_run(objects, run_id, epoch).status in (
        Status.QUEUED,
        Status.RUNNING,
    ) or _winding_down(simulator, run_id, epoch):
        raise Conflict(f"run {run_id}, epoch {epoch} is being computed: wait for it, or stop it")
    simulator.positions.close_over(run_id, epoch)
    delete_stored_epoch(objects, run_id, epoch)
    return {"deleted": f"{run_id}/{epoch}"}


def _winding_down(simulator: Simulator, run_id: str, epoch: int) -> bool:
    """Whether a playback replaced by another, told to stop, is still writing
    an epoch."""
    return any(found.has_epoch(run_id, epoch) for found in simulator.playbacks.retiring())


def _stored(simulator: Simulator, run_id: str, epoch: int) -> StoredEpoch:
    return StoredEpoch(simulator, _objects(simulator), run_id, epoch)


def _at(epoch: StoredEpoch, at_s: float | None) -> float:
    return epoch.frontier_s() if at_s is None else at_s


def epoch_observations(
    simulator: Simulator,
    run_id: str,
    epoch: int,
    *,
    after: int | None,
    limit: int | None,
    at_s: float | None,
) -> ObservationBatch:
    """An epoch's observations after a cursor that were delivered by `at_s`
    into its run, by default its frontier."""
    cursor, most = batch_cursor(after), batch_limit(limit)
    kept = _stored(simulator, run_id, epoch)
    moment = _at(kept, at_s)
    return _observations(kept, cursor, kept.observations(cursor, most, moment), moment)


def epoch_events(
    simulator: Simulator,
    run_id: str,
    epoch: int,
    *,
    after: int | None,
    limit: int | None,
    at_s: float | None,
) -> EventBatch:
    cursor, most = batch_cursor(after), batch_limit(limit)
    kept = _stored(simulator, run_id, epoch)
    moment = _at(kept, at_s)
    return _events(kept, cursor, kept.events(cursor, most, moment), moment)


def epoch_outcomes(
    simulator: Simulator,
    run_id: str,
    epoch: int,
    *,
    after: int | None,
    limit: int | None,
    at_s: float | None,
) -> OutcomeBatch:
    cursor, most = batch_cursor(after), batch_limit(limit)
    kept = _stored(simulator, run_id, epoch)
    moment = _at(kept, at_s)
    return _outcomes(kept, cursor, kept.outcomes(cursor, most, moment), moment)


def _observations(
    kept: StoredEpoch, after: int, found: Records[Observation], moment_s: float
) -> ObservationBatch:
    return ObservationBatch(
        run_id=kept.run_id,
        epoch=kept.epoch,
        after=after,
        next=found.next,
        simulated_now=kept.start + timedelta(seconds=moment_s),
        has_more=found.has_more,
        observations=found.records,
    )


def _events(kept: StoredEpoch, after: int, found: Records[Event], moment_s: float) -> EventBatch:
    return EventBatch(
        run_id=kept.run_id,
        epoch=kept.epoch,
        after=after,
        next=found.next,
        simulated_now=kept.start + timedelta(seconds=moment_s),
        has_more=found.has_more,
        events=found.records,
    )


def _outcomes(
    kept: StoredEpoch, after: int, found: Records[ActionOutcome], moment_s: float
) -> OutcomeBatch:
    return OutcomeBatch(
        run_id=kept.run_id,
        epoch=kept.epoch,
        after=after,
        next=found.next,
        simulated_now=kept.start + timedelta(seconds=moment_s),
        has_more=found.has_more,
        outcomes=found.records,
    )


def open_position(
    simulator: Simulator, run_id: str, epoch: int, seconds_per_day: float | None = None
) -> PositionState:
    """A new position at the start of a stored epoch, or for a fork at the moment
    it was made from, paused. One with files missing is refused in words: a list
    counts its folders and can miss a lost file, and here its objects are looked
    at, before a read comes to the gap."""
    objects = _objects(simulator)
    if epoch in stored_epochs(objects, run_id) and stored_run(objects, run_id, epoch).damaged:
        raise Conflict(
            f"files of run {run_id}, epoch {epoch} are missing, so it cannot be read whole"
        )
    return simulator.positions.open(
        simulator,
        objects,
        run_id,
        epoch,
        seconds_per_day=DEFAULT_SECONDS_PER_DAY if seconds_per_day is None else seconds_per_day,
    ).state()


def _position(simulator: Simulator, position_id: str) -> Position:
    return simulator.positions.get(position_id)


def position(simulator: Simulator, position_id: str) -> PositionState:
    return _position(simulator, position_id).state()


def play(simulator: Simulator, position_id: str) -> PositionState:
    return _position(simulator, position_id).play()


def pause(simulator: Simulator, position_id: str) -> PositionState:
    return _position(simulator, position_id).pause()


def follow(simulator: Simulator, position_id: str) -> PositionState:
    return _position(simulator, position_id).follow()


def set_pace(simulator: Simulator, position_id: str, seconds_per_day: float) -> PositionState:
    return _position(simulator, position_id).set_pace(seconds_per_day)


def seek(simulator: Simulator, position_id: str, time_s: float) -> PositionState:
    return _position(simulator, position_id).seek(time_s)


def close(simulator: Simulator, position_id: str) -> None:
    simulator.positions.close(position_id)


def position_observations(
    simulator: Simulator, position_id: str, after: int | None, limit: int | None
) -> ObservationBatch:
    """The observations after a cursor that the position's epoch delivered by
    its moment."""
    cursor, most = batch_cursor(after), batch_limit(limit)
    held = _position(simulator, position_id)
    moment = held.state().time_s
    return _observations(held.epoch, cursor, held.epoch.observations(cursor, most, moment), moment)


def position_events(
    simulator: Simulator, position_id: str, after: int | None, limit: int | None
) -> EventBatch:
    cursor, most = batch_cursor(after), batch_limit(limit)
    held = _position(simulator, position_id)
    moment = held.state().time_s
    return _events(held.epoch, cursor, held.epoch.events(cursor, most, moment), moment)


def position_outcomes(
    simulator: Simulator, position_id: str, after: int | None, limit: int | None
) -> OutcomeBatch:
    cursor, most = batch_cursor(after), batch_limit(limit)
    held = _position(simulator, position_id)
    moment = held.state().time_s
    return _outcomes(held.epoch, cursor, held.epoch.outcomes(cursor, most, moment), moment)
