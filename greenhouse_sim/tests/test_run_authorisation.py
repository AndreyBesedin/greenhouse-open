"""Who may act on a simulator's runs (P13.4, decision 0052): an
authorisation the server is given as a file, or else the local operator's;
enforced by every playback's gateway when a plan is given and when each of
its actions falls due, and changed while runs play, each change recorded."""

import argparse
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind
from greenhouse_protocol.authorisation import (
    AuthorisationConfig,
    AuthorisationGroup,
    Grant,
    TargetSelector,
)
from greenhouse_protocol.outcome import OutcomeStatus

from greenhouse_sim.api import server
from greenhouse_sim.services import playback
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.gateway import (
    LOCAL_AUTHORISATION,
    LOCAL_OPERATOR,
    authorisation_file,
)
from greenhouse_sim.services.playback import (
    TARGETS_PLAN,
    Epochs,
    Playback,
    PlaybackCommand,
    delivered,
)
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

SCENARIO: Final = "reference_greenhouse"
# Every record there is, in one batch.
ALL: Final = 10**6
# The local operator, allowed to set levels and nothing else.
LEVELS_ONLY: Final = AuthorisationConfig(
    version=2,
    groups=(
        AuthorisationGroup(
            group_id="local_operators",
            principals=frozenset({LOCAL_OPERATOR}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
    ),
)


class _Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# The local operator, allowed every kind, in the configuration's next
# version.
EVERY_KIND: Final = LOCAL_AUTHORISATION.model_copy(update={"version": 2})
# The local operator, allowed to set the day's heating target, and no other.
DAY_TARGET_ONLY: Final = AuthorisationConfig(
    version=3,
    groups=(
        AuthorisationGroup(
            group_id="local_operators",
            principals=frozenset({LOCAL_OPERATOR}),
            grants=(
                Grant(
                    kinds=frozenset({ActionKind.SET_TARGET}),
                    targets=TargetSelector(targets=frozenset({"heating_day"})),
                ),
            ),
        ),
    ),
)


@pytest.fixture
def levels_only() -> Iterator[Simulator]:
    with Simulator(authorisation=LEVELS_ONLY) as made:
        yield made


def test_an_authorisation_is_read_from_its_file(tmp_path: Path) -> None:
    given = tmp_path / "authorisation.json"
    given.write_text(LEVELS_ONLY.model_dump_json(indent=2))

    assert authorisation_file(given) == LEVELS_ONLY


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("{not json", "not an authorisation in"),
        ('{"version": 0, "groups": []}', "version"),
        ('{"version": 1}', "groups"),
    ],
)
def test_a_file_that_is_no_authorisation_is_refused_saying_why(
    tmp_path: Path, text: str, said: str
) -> None:
    given = tmp_path / "authorisation.json"
    given.write_text(text)

    with pytest.raises(InvalidRequest, match=said):
        authorisation_file(given)
    with pytest.raises(InvalidRequest, match="no authorisation read from"):
        authorisation_file(tmp_path / "missing.json")


def test_the_server_takes_the_authorisation_it_is_given_or_the_local_operators(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = argparse.ArgumentParser()
    given = tmp_path / "authorisation.json"
    given.write_text(LEVELS_ONLY.model_dump_json())

    assert server._authorisation(None, parser) == LOCAL_AUTHORISATION
    assert server._authorisation(given, parser) == LEVELS_ONLY
    # One it cannot read stops it starting, saying why.
    given.write_text("{}")
    with pytest.raises(SystemExit):
        server._authorisation(given, parser)
    assert "not an authorisation in" in capsys.readouterr().err


def test_an_action_its_principal_may_not_do_is_refused_when_its_plan_is_given(
    levels_only: Simulator,
) -> None:
    """The local operator, allowed levels only, may not change a target: the
    change is refused, saying who may not do what, and the run is as it was."""
    played = Playback(levels_only, SCENARIO, seconds_per_day=24.0, clock=_Clock())

    with pytest.raises(InvalidRequest, match="local_operator is not authorised to set_target"):
        played.set_targets({"heating_night": 22.0})
    assert played.state().targets == []


def test_target_changes_the_local_operator_may_not_all_make_are_refused_whole() -> None:
    """Allowed the day's target and not the night's, the local operator is
    refused both, and the run is as it was: no change is half made."""
    with Simulator(authorisation=DAY_TARGET_ONLY) as simulator:
        played = Playback(simulator, SCENARIO, seconds_per_day=24.0, clock=_Clock())

        with pytest.raises(
            InvalidRequest, match="local_operator is not authorised to set_target heating_night"
        ):
            played.set_targets({"heating_day": 22.0, "heating_night": 18.0})
        assert played.state().targets == []
        with pytest.raises(NotFound):
            played.plan(TARGETS_PLAN)
        assert played.set_targets({"heating_day": 22.0}).targets != []


def test_one_change_of_a_simulators_authorisation_at_a_time(
    finishes_beside_held: Callable[[AbstractContextManager[bool], Callable[[], object]], bool],
) -> None:
    """A change waits while another is being made, so that the simulator's
    authorisation and every playback's take the changes in one order."""
    with Simulator() as simulator:
        assert not finishes_beside_held(
            simulator._authorising, lambda: simulator.authorise(LEVELS_ONLY)
        )
        assert simulator.authorisation == LEVELS_ONLY


def test_an_authorisation_changed_while_runs_play_holds_from_then_and_is_recorded(
    tmp_path: Path,
) -> None:
    with Simulator() as simulator:
        playback.start(
            simulator, SCENARIO, 24.0, clock=_Clock(), hold=True, epochs=Epochs(tmp_path)
        )
        played = playback.playback(simulator, SCENARIO)
        played.set_targets({"heating_night": 22.0})

        simulator.authorise(LEVELS_ONLY)

        changes = played.plan(TARGETS_PLAN).authorisation
        assert [change.version for change in changes] == [1, 2]
        with pytest.raises(InvalidRequest, match="not authorised to set_target"):
            played.set_targets({"heating_day": 24.0})
        # A playback started from then on takes it from its start, and so
        # does one started over: its record begins again there.
        played.command(PlaybackCommand.RESTART)
        assert simulator.authorisation == LEVELS_ONLY
        simulator.authorise(EVERY_KIND)
        played.command(PlaybackCommand.RESTART)
        played.set_targets({"heating_day": 24.0})
        assert [(c.version, c.at) for c in played.plan(TARGETS_PLAN).authorisation] == [
            (2, played.start)
        ]


@pytest.mark.slow
def test_a_change_whose_rights_are_withdrawn_before_it_falls_due_is_refused_then(
    tmp_path: Path,
) -> None:
    """Set for 6 h 01 at 6 h 00 min 30 s, the night's target is pending when
    the local operator loses the right to set targets: when it falls due it
    is refused, and the run goes on without it."""
    clock = _Clock()
    with Simulator() as simulator:
        playback.start(simulator, SCENARIO, 24.0, clock=clock, hold=True, epochs=Epochs(tmp_path))
        played = playback.playback(simulator, SCENARIO)
        assert played.work_day(0)
        played.command(PlaybackCommand.PLAY)
        clock.now = 6.0 + 30.0 / HOUR_S
        assert played.set_targets({"heating_night": 22.0}).targets != []

        simulator.authorise(LEVELS_ONLY)
        assert played.work_day(0)
        clock.now = 7.0

        (refused,) = played.plan(TARGETS_PLAN).outcomes
        assert refused.status == OutcomeStatus.REFUSED
        assert refused.reason == "local_operator is no longer authorised"
        assert played.state().targets == []
        # Its records were worked out with the change: the clock waits at
        # its moment, and nothing after it is delivered, until they are
        # worked out again without it, as the scenario's own run's.
        due = played.start + timedelta(seconds=6 * HOUR_S + 60)
        assert played.state().simulated_now == due
        assert max(delivered(r) for r in played.records_after(0, ALL).records) <= due
        assert played.work_day(0)
        clock.now = 8.0
        own_clock = _Clock()
        own = Playback(simulator, SCENARIO, seconds_per_day=24.0, clock=own_clock)
        assert own.work_day(0)
        own.command(PlaybackCommand.PLAY)
        own_clock.now = 8.0
        until = played.start + timedelta(hours=7)
        assert _readings(played, due, until) == _readings(own, due, until) != []


def _readings(
    played: Playback, after: datetime, until: datetime
) -> list[tuple[str | None, datetime, float]]:
    """The sensors' readings a playback delivered by its clock after
    `after`, up to `until`."""
    return [
        (record.sensor_id, record.timestamp, record.value)
        for record in played.records_after(0, ALL).records
        if record.sensor_id is not None and after < delivered(record) <= until
    ]
