"""A run's heating targets changed from a moment on (#274): its thermostat
heats to them from then, the house's air within its band; the changes are
part of the run, so that another target makes another run and the same
targets the same run; a checkpoint keeps those before its day; and a
playback's run, steered while it plays, keeps its identity and epoch and
rewrites nothing it delivered (decision 0043)."""

import json
from http import HTTPStatus
from typing import Any, Final

import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Command, Schedule, TargetChange
from greenhouse_sim.climate.thermostat import Thermostat
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.equipment import Target
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run, climate_run, house_air_at
from greenhouse_sim.services.heat_log import heat_records
from greenhouse_sim.services.playback import Playback, PlaybackCommand
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

SCENARIO: Final = "reference_greenhouse"
# Its day starts at 7 h, its thermostat heating to 18 °C by day.
DAY_FROM_S: Final = 7 * HOUR_S
WARMER: Final = ((DAY_FROM_S, "heating_day", 24.0),)
EVERY_S: Final = 300.0
ALL: Final = 10**6


class Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _equipment(simulator: Simulator, query: str) -> Any:
    response = respond(simulator, "GET", f"/api/scenarios/{SCENARIO}/climate/equipment?{query}")
    assert response.status == HTTPStatus.OK, response.body
    return response.body


def test_a_schedule_keeps_target_changes_in_order_and_tells_runs_apart_by_them() -> None:
    commands = [Command(time_s=0.0, actuator_id="fan", level=1.0)]
    warmer = TargetChange(time_s=3600.0, target=Target.HEATING_DAY, value_c=24.0)
    cooler = TargetChange(time_s=7200.0, target=Target.HEATING_DAY, value_c=20.0)
    schedule = Schedule.of(commands, [cooler, warmer])

    assert schedule.targets == (warmer, cooler)
    assert schedule.targets_at(3599.0) == {}
    assert schedule.targets_at(3600.0) == {Target.HEATING_DAY: 24.0}
    assert schedule.targets_at(9000.0) == {Target.HEATING_DAY: 20.0}
    # The same commands: the same run until the first change one makes.
    assert schedule.same_until(Schedule.of(commands)) == 3600.0
    assert schedule.same_until(Schedule.of(commands, [warmer])) == 7200.0
    assert schedule.same_until(schedule) == float("inf")
    with pytest.raises(ValidationError, match="on the minute"):
        TargetChange(time_s=90.0, target=Target.HEATING_DAY, value_c=24.0)


def test_the_thermostat_heats_to_its_targets_as_changed() -> None:
    thermostat = Thermostat(actuator_id="heater", day_c=18.0, night_c=16.0)
    changed = {Target.HEATING_DAY: 24.0}

    assert thermostat.setpoints_c(changed) == (24.0, 16.0)
    assert thermostat.setpoint_c(DAY_FROM_S, changed) == 24.0
    assert thermostat.setpoint_c(DAY_FROM_S - 60.0, changed) == 16.0
    assert thermostat.heats(23.0, False, DAY_FROM_S, changed)
    assert not thermostat.heats(23.0, False, DAY_FROM_S)


def test_the_house_is_heated_to_a_target_set_and_says_its_setpoints(simulator: Simulator) -> None:
    """Set to 24 °C from 7 h, the house's air is within the thermostat's band
    of it by 8 h 30, where the scenario's own 18 °C holds it near 18."""
    half_band = 0.5
    moment = DAY_FROM_S + 1.5 * HOUR_S
    own = house_air_at(RunRequest(SCENARIO), moment)
    warmer = house_air_at(RunRequest(SCENARIO, targets=WARMER), moment)
    assert own is not None and warmer is not None

    assert abs(own.temperature_c - 18.0) <= half_band
    assert abs(warmer.temperature_c - 24.0) <= half_band
    said = _equipment(simulator, f"t={moment:.0f}&targets={DAY_FROM_S:.0f}:heating_day:24")[
        "thermostat"
    ]
    assert (said["setpoint_c"], said["day_c"], said["night_c"]) == (24.0, 24.0, 16.0)
    assert _equipment(simulator, f"t={moment:.0f}")["thermostat"]["day_c"] == 18.0


def test_another_target_makes_another_run_and_the_same_targets_the_same() -> None:
    own_key, _ = climate_run(RunRequest(SCENARIO))
    warmer_key, _ = climate_run(RunRequest(SCENARIO, targets=WARMER))

    assert warmer_key != own_key
    assert climate_run(RunRequest(SCENARIO, targets=WARMER))[0] == warmer_key
    own_id = air_through_a_run(RunRequest(SCENARIO))[1]
    assert air_through_a_run(RunRequest(SCENARIO, targets=WARMER))[1] != own_id
    # A run whose targets are its scenario's own is named as before #274.
    assert air_through_a_run(RunRequest(SCENARIO, targets=()))[1] == own_id


def test_the_same_target_changes_asked_for_in_another_order_make_the_same_run() -> None:
    later = (DAY_FROM_S + HOUR_S, "heating_day", 20.0)
    in_order = RunRequest(SCENARIO, targets=(*WARMER, later))
    reversed_ = RunRequest(SCENARIO, targets=(later, *WARMER))

    assert climate_run(reversed_)[0] == climate_run(in_order)[0]
    assert air_through_a_run(reversed_)[1] == air_through_a_run(in_order)[1]


@pytest.mark.parametrize(
    ("targets", "refused"),
    [
        ("30:heating_day:24", "on the minute"),
        ("60:cooling:24", "a target is one of heating_day, heating_night, not 'cooling'"),
        ("60:heating_day:55", "lies from 0 to 40 °C, not 55"),
        ("60:heating_day", "targets wants seconds:target:celsius commands"),
        (f"{200 * DAY_S:.0f}:heating_day:24", "within the run"),
    ],
)
def test_a_target_change_that_does_not_fit_is_refused(
    simulator: Simulator, targets: str, refused: str
) -> None:
    response = respond(
        simulator, "GET", f"/api/scenarios/{SCENARIO}/climate/equipment?t=60&targets={targets}"
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert refused in str(response.body)


def test_a_scenario_without_a_heating_loop_has_no_target_to_change(simulator: Simulator) -> None:
    response = respond(
        simulator,
        "GET",
        "/api/scenarios/climate_box/climate/equipment?t=60&targets=60:heating_day:24",
    )

    assert response.body == {"error": "climate_box has no heating loop whose target to change"}


def test_a_format_2_checkpoint_is_read_as_one_whose_run_changed_no_target() -> None:
    kept = checkpoints.load_opening(SCENARIO)[0]
    document = json.loads(checkpoints.checkpoint(kept.checkpoint_id).model_dump_json())
    assert document["checkpoint_format"] == checkpoints.CHECKPOINT_FORMAT == 3

    older = {key: value for key, value in document.items() if key != "targets"}
    uploaded = checkpoints.upload_checkpoint(older | {"checkpoint_format": 2})
    assert uploaded.targets == []
    with pytest.raises(InvalidRequest, match="a format 2 checkpoint keeps no target changes"):
        checkpoints.upload_checkpoint(document | {"checkpoint_format": 2, "targets": [[0, "x", 1]]})


@pytest.mark.slow
def test_a_checkpoint_keeps_the_target_changes_before_its_day() -> None:
    later = ((DAY_S + DAY_FROM_S, "heating_day", 20.0),)
    run = RunRequest(SCENARIO, targets=(*WARMER, *later))
    saved = checkpoints.save_checkpoint(run, time_s=DAY_S)
    kept = checkpoints.checkpoint(saved.checkpoint_id)

    assert [tuple(change) for change in kept.targets] == list(WARMER)
    assert saved.targets == kept.targets
    # Restored and given its later changes again, it is the same run.
    restored = kept.run()
    assert restored.targets == WARMER
    assert (
        climate_run(RunRequest(SCENARIO, targets=(*restored.targets, *later)))[0]
        == (climate_run(run)[0])
    )


@pytest.mark.slow
def test_a_target_set_while_the_run_plays_steers_it_from_the_next_minute() -> None:
    """Set at 6 h 00 min 30 s, the night's target holds from 6 h 01 in the
    same run and epoch: the clock waits there until the day is worked out
    again, nothing delivered before changes, and the heater gives more heat
    in the hour after."""
    clock = Clock()
    played = Playback(SCENARIO, seconds_per_day=24.0, every_s=EVERY_S, clock=clock)
    assert played.work_day(0)
    played.command(PlaybackCommand.PLAY)
    clock.now = 6.0 + 30.0 / HOUR_S
    before = played.state()
    delivered = played.records_after(0, ALL)

    steered = played.set_targets({"heating_night": 22.0})
    change = (6 * HOUR_S + 60.0, "heating_night", 22.0)
    assert steered.targets == [change]
    assert (steered.run_id, steered.epoch) == (before.run_id, before.epoch)
    # Worked out, under its targets as they are, only up to the change.
    assert steered.worked_out_s == change[0]

    clock.now = 12.0
    assert played.state().time_s == change[0]
    assert played.work_day(0)
    assert played.state().worked_out_s == DAY_S
    # It plays on from there: the time it waited is not banked.
    clock.now = 13.0
    assert played.state().time_s == change[0] + HOUR_S
    again = played.records_after(0, ALL)
    assert again.records[: len(delivered.records)] == delivered.records

    start = run_start(SCENARIO)
    own = heat_records(RunRequest(SCENARIO), 0, start, before.run_id)
    warmer = heat_records(RunRequest(SCENARIO, targets=(change,)), 0, start, before.run_id)
    assert [record.value for record in warmer[:6]] == [record.value for record in own[:6]]
    assert warmer[6].value > own[6].value
    # What it delivers after the change is the steered run's, though the day
    # was read back before it.
    delivered_heat = [r for r in again.records if r.observation_id == warmer[6].observation_id]
    assert [r.value for r in delivered_heat] == [warmer[6].value]
    # Started over, it is the scenario's own run again.
    assert played.command(PlaybackCommand.RESTART).targets == []
