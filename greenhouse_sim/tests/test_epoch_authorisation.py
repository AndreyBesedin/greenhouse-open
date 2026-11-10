"""An epoch keeps its authorisation (decision 0072): the rights it begins
under and each change of them are entries of its log, applied again at their
moments, so that a worker, a resume and a fork decide every action under the
rights in force when it was decided; and a change made while a worker computes
an epoch reaches it through the store."""

import json
import sys
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import At, Plan, PlannedAction

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import forks, interventions, scheduler
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Status
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Stepped, execute, queued, resume
from greenhouse_sim.units import HOUR_S

sys.path.insert(0, str(Path(__file__).parent))

import short_runs

BOX: Final = "climate_box_rights"
DAYS: Final = 2
END_S: Final = DAYS * DAY_S
NOON_S: Final = 12 * HOUR_S
# The heater's noon, once the right to set levels has been withdrawn.
NOON_REFUSED: Final = ("noon", OutcomeStatus.REFUSED, "local_operator is no longer authorised")
# A level asked while the right to set levels is withheld.
NOT_AUTHORISED: Final = "local_operator is not authorised to set_level"
# The local operator, allowed every kind but setting levels: a server's file.
NO_LEVELS: Final = AuthorisationConfig(
    version=2,
    groups=(
        AuthorisationGroup(
            group_id="local_operators",
            principals=frozenset({LOCAL_OPERATOR}),
            grants=(Grant(kinds=frozenset(ActionKind) - {ActionKind.SET_LEVEL}),),
        ),
    ),
)
# How a log says the authorisation `NO_LEVELS`.
SAID: Final = {"kind": "authorisation", "authorisation": NO_LEVELS.model_dump(mode="json")}


def _simulator(**given: object) -> Simulator:
    """A simulator that knows the two-day one-plant box: a new one is a process
    started again, as a worker's is, unless it is given an authorisation."""
    made = Simulator(**given)  # type: ignore[arg-type]
    made.catalogue.register(short_runs.one_plant_box(BOX, DAYS))
    return made


@pytest.fixture
def worker() -> Iterator[Simulator]:
    """A worker's own simulator, the local operator's, as `scheduler.work` makes."""
    with _simulator() as made:
        yield made


def _noon(epoch: EpochStore, simulator: Simulator) -> Plan:
    """The heater on at noon of the first day, by the local operator."""
    start = run_start(simulator.catalogue, BOX)
    return Plan(
        plan_id="noon",
        run_id=epoch.run_id,
        epoch=epoch.epoch,
        revision=1,
        actions=(
            PlannedAction(
                action_id="heat",
                action=SetLevel(device_id="heater", level=1.0),
                timing=At(at=start + timedelta(seconds=NOON_S)),
                proposed_by=LOCAL_OPERATOR,
            ),
        ),
    )


def _given(plan: Plan) -> bytes:
    return interventions.ASKED.dump_json(interventions.PlanGiven(plan=plan))


def _ended(epoch: EpochStore) -> list[tuple[str, OutcomeStatus, str | None]]:
    """What became of each action, by its plan: those its outcomes kept say."""
    return [(o.plan_id, o.status, o.reason) for o in epoch.outcomes().records]


def _digests(epoch: EpochStore) -> list[str]:
    return [commit.digest for commit in epoch.commits()]


def _worked_by_a_process(epoch: EpochStore, root: Path) -> None:
    """The epoch worked out as a scheduler's worker works it: in a simulator of
    its own, from what the store holds."""
    with pytest.raises(SystemExit) as ended:
        scheduler.work(str(root), epoch.run_id, epoch.epoch)
    assert ended.value.code == 0


def test_a_workers_epoch_refuses_what_the_servers_authorisation_withholds(
    tmp_path: Path,
) -> None:
    """A server given a file that withholds levels starts a run that a worker
    computes: a level asked of it through the store is refused there, as the
    server's own playback refuses it, and the heater is never set."""
    with _simulator(authorisation=NO_LEVELS, runs=FolderStore(tmp_path)) as server:
        epoch = queued(server, FolderStore(tmp_path), BOX)
        # Written to the store as any process may: the store is the only channel.
        asked = epoch.ask({"kind": "levels", "levels": {"heater": 1.0}})
    _worked_by_a_process(epoch, tmp_path)

    assert epoch.manifest().status == Status.FINISHED
    assert _ended(epoch) == [(f"levels_{asked}", OutcomeStatus.REFUSED, NOT_AUTHORISED)]


def test_a_change_of_authorisation_made_while_a_worker_computes_reaches_it(
    tmp_path: Path, worker: Simulator
) -> None:
    """The heater, set for noon while levels were allowed, is refused at noon
    when the server withdraws the right at 6 h while a worker computes the
    epoch: the change reaches it through the store, in the order it was asked
    among the changes, and its log says when. A level asked after it is refused."""
    later: list[str] = []
    with _simulator(runs=FolderStore(tmp_path)) as server:
        epoch = queued(server, FolderStore(tmp_path), BOX)
        interventions.ask(server, epoch.run_id, epoch.epoch, _given(_noon(epoch, server)))

        def barriers() -> Iterator[float]:
            yield 6 * HOUR_S
            server.authorise(NO_LEVELS)
            # Through the store, past the server's own check: the worker decides.
            later.append(epoch.ask({"kind": "levels", "levels": {"heater": 0.5}}))
            yield DAY_S
            yield END_S

        assert execute(worker, epoch, Stepped(barriers())) == Status.FINISHED

    assert [(entry.what["kind"], entry.given_s) for entry in epoch.logged()] == [
        ("plan", 0.0),
        ("authorisation", 6 * HOUR_S),
        ("plan", 6 * HOUR_S),
    ]
    assert _ended(epoch) == [
        (f"levels_{later[0]}", OutcomeStatus.REFUSED, NOT_AUTHORISED),
        NOON_REFUSED,
    ]


def _withdrawn_at_six(simulator: Simulator, root: Path, *, to_s: float = DAY_S) -> EpochStore:
    """An epoch played here, the heater set for noon, the right to set levels
    withdrawn at 6 h, kept through `to_s` and, unless that is its end, interrupted."""
    played = Playback(simulator, BOX, epochs=Epochs(root))
    state = played.state()
    epoch = EpochStore(FolderStore(root), state.run_id, state.epoch)
    played.submit(_noon(epoch, simulator))
    played.step_to(6 * HOUR_S)
    played.authorise(NO_LEVELS)
    played.step_to(min(to_s + HOUR_S, END_S))
    played.keep()
    if to_s < END_S:
        epoch.set_status(Status.INTERRUPTED)
    return epoch


def test_an_epoch_whose_rights_were_withdrawn_is_carried_on_to_its_end(
    tmp_path: Path, worker: Simulator
) -> None:
    """P13's criterion 8, carried on: the epoch's first day is kept with the
    heater refused at noon, and a worker of the local operator's carries it on
    from its checkpoint to its end, with the outcome it kept: the epoch that
    was never interrupted, digest for digest."""
    with _simulator() as played_here:
        epoch = _withdrawn_at_six(played_here, tmp_path / "interrupted")
        whole = _withdrawn_at_six(played_here, tmp_path / "whole", to_s=END_S)
    kept = _ended(epoch)

    assert resume(worker, epoch, Free()) == Status.FINISHED
    assert kept == [NOON_REFUSED]
    assert _ended(epoch) == kept == _ended(whole)
    assert len(epoch.commits()) == DAYS
    assert _digests(epoch) == _digests(whole)
    epoch.verify()


def test_a_fork_after_a_withdrawal_starts_under_the_withdrawn_rights(
    tmp_path: Path, worker: Simulator
) -> None:
    """Forked at 8 h, after levels were withdrawn and before the heater's noon,
    by a server whose rights are those, the fork refuses the heater at noon as
    its parent did, though its worker is the local operator's: the withdrawal
    is among the entries it inherits, and nothing is added to them."""
    with _simulator() as played_here:
        parent = _withdrawn_at_six(played_here, tmp_path)
    with _simulator(authorisation=NO_LEVELS) as server:
        fork = forks.fork(server, FolderStore(tmp_path), parent.run_id, parent.epoch, 8 * HOUR_S)

    assert [entry.what["kind"] for entry in fork.logged()] == ["plan", "authorisation"]
    assert resume(worker, fork, Free()) == Status.FINISHED
    assert _ended(fork) == [NOON_REFUSED]


def test_a_fork_goes_on_under_the_rights_of_the_simulator_that_forks_it(
    tmp_path: Path, worker: Simulator
) -> None:
    """Forked at 8 h by a simulator of the local operator's, which may set
    levels, the same epoch's fork goes on under its rights from its instant,
    the rights its changes are checked under: the heater is set at noon."""
    with _simulator() as played_here:
        parent = _withdrawn_at_six(played_here, tmp_path)
        fork = forks.fork(
            played_here, FolderStore(tmp_path), parent.run_id, parent.epoch, 8 * HOUR_S
        )

    *_, given = fork.logged()
    assert (given.what["kind"], given.given_s) == ("authorisation", 8 * HOUR_S)
    # The rights it is given are its own, not among those it inherits.
    assert fork.manifest().fork.inherited == 2  # type: ignore[union-attr]
    assert len(fork.logged()) == 3
    assert resume(worker, fork, Free()) == Status.FINISHED
    assert _ended(fork) == [("noon", OutcomeStatus.EXECUTED, None)]


def test_an_epoch_begun_under_other_rights_than_the_local_operators_says_so_first(
    tmp_path: Path,
) -> None:
    """Queued or played under a server's file, an epoch's log begins with it, and
    so does the next epoch a restart opens; under the local operator's rights,
    the log says nothing of them, and keeps the bytes and the digest it had."""
    with _simulator(authorisation=NO_LEVELS, runs=FolderStore(tmp_path / "file")) as server:
        given = queued(server, FolderStore(tmp_path / "file"), BOX)
        played = Playback(server, BOX, epochs=Epochs(tmp_path / "played"))
        played.begin()
        played.command(PlaybackCommand.RESTART)
        played.stop()
    with _simulator() as local:
        plain = queued(local, FolderStore(tmp_path / "local"), BOX)

    restarted = [EpochStore(FolderStore(tmp_path / "played"), given.run_id, n) for n in (0, 1)]
    begun = [each.logged()[0] for each in (given, *restarted)]
    assert [(entry.seq, entry.given_s, entry.what) for entry in begun] == [(0, 0.0, SAID)] * 3
    assert plain.logged() == []


def test_the_api_asks_no_change_of_authorisation(tmp_path: Path) -> None:
    """The authorisation is the server's input (decision 0052): a change of it
    asked of an epoch through the API's route is not a change it takes."""
    with _simulator(runs=FolderStore(tmp_path)) as server:
        epoch = queued(server, FolderStore(tmp_path), BOX)
        body = json.dumps(SAID).encode()

        with pytest.raises(InvalidRequest, match="not a change"):
            interventions.ask(server, epoch.run_id, epoch.epoch, body)
    assert epoch.requests() == []


def test_an_epoch_kept_with_no_authorisation_in_its_log_is_carried_on(
    tmp_path: Path, worker: Simulator
) -> None:
    """An epoch whose log names no authorisation, as every epoch kept before
    did, began under the local operator's rights, which every worker had then:
    its heater, set at noon, is carried on as kept, even by a simulator whose
    own rights withhold levels."""
    epoch = queued(worker, FolderStore(tmp_path), BOX)
    epoch.ask(json.loads(_given(_noon(epoch, worker))))
    assert execute(worker, epoch, Stepped([DAY_S])) == Status.INTERRUPTED
    assert [entry.what["kind"] for entry in epoch.logged()] == ["plan"]
    kept = _ended(epoch)

    with _simulator(authorisation=NO_LEVELS) as other:
        assert resume(other, epoch, Free()) == Status.FINISHED

    assert kept == [("noon", OutcomeStatus.EXECUTED, None)]
    assert _ended(epoch) == kept
