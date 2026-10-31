"""The run a request asks for (audit W11, `AUDIT.6`), read once from its
query and taken by every service that takes a run: its identity apart from
the moment and the window, its commands in their order, same-time ones too,
no daily commands apart from its scenario's own, its defaults and errors as
they were, and a checkpoint's run the run it was saved from, in the
checkpoint's own format."""

import dataclasses
import json
import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import Any, Final, get_args

import pytest
from greenhouse_protocol.actions import HEATING_SETPOINT_RANGE_C, SetLevel, SetTarget
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.equipment import Target
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.climate_readings import EquipmentAt
from greenhouse_sim.services.climate_runs import SETPOINT_RANGE_C, climate_run
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.runs import (
    Commanded,
    PlannedAt,
    PlannedDaily,
    RunPlan,
    RunRequest,
)
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

# Every route that makes or keeps a run, by its method and its path after
# the scenario's.
RUN_ROUTES: Final = [
    ("GET", "fields/climate"),
    ("GET", "climate/probes"),
    ("GET", "climate/house"),
    ("GET", "climate/glazing"),
    ("GET", "climate/openings"),
    ("GET", "climate/plants"),
    ("GET", "crop"),
    ("GET", "crop/plant_0"),
    ("GET", "climate/observations"),
    ("GET", "climate/equipment"),
    ("GET", "climate/state"),
    ("GET", "climate/truth"),
    ("GET", "timeline"),
    ("POST", "checkpoints"),
]
# A malformed part of a run, and how each route refuses it.
MALFORMED: Final = {
    "set=fan": "set wants key:number pairs, not 'fan'",
    "open=roof_vent": "open wants key:number pairs, not 'roof_vent'",
    "schedule=60:fan": "schedule wants seconds:actuator:level commands, not '60:fan'",
    "daily=60:fan": "daily wants seconds:actuator:level commands, not '60:fan'",
}
# The scenario whose opening days are kept, in format 3.
REFERENCE: Final = "reference_greenhouse"
# 9 h, when the reference greenhouse's daily commands have its fans on.
MORNING_S: Final = 9 * HOUR_S


def _levels(simulator: Simulator, query: str, scenario_id: str = "climate_box") -> dict[str, float]:
    response = respond(simulator, "GET", f"/api/scenarios/{scenario_id}/climate/equipment?{query}")
    assert response.status == HTTPStatus.OK, response.body
    return EquipmentAt.model_validate(response.body).levels


def test_a_run_is_its_parts_and_not_its_moment() -> None:
    parts = [part.name for part in dataclasses.fields(RunRequest)]

    assert parts == [
        "scenario_id",
        "layout",
        "weather",
        "levels",
        "openings",
        "plan",
        "seed",
    ]


def _climate_runs_made(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The climate runs the services made, as their log names them."""
    return [
        getattr(record, "label", "")
        for record in caplog.records
        if (getattr(record, "store", None), getattr(record, "event", None))
        == ("climate runs", "made")
    ]


def test_a_run_asked_for_at_other_moments_and_windows_is_one_run(
    simulator: Simulator, afresh: Callable[[], None], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="greenhouse_sim")
    asked = "/api/scenarios/climate_box/climate/house?set=heater:1&schedule=600:fan:1"
    assert respond(simulator, "GET", f"{asked}&t=0").status == HTTPStatus.OK
    assert _climate_runs_made(caplog)
    caplog.clear()

    for moment in ("t=300", "t=1200", "t=1200&from=600"):
        assert respond(simulator, "GET", f"{asked}&{moment}").status == HTTPStatus.OK
    assert (
        respond(simulator, "GET", asked.replace("house", "equipment") + "&t=900").status
        == HTTPStatus.OK
    )

    assert _climate_runs_made(caplog) == []


def test_commands_keep_their_order_same_time_ones_too(simulator: Simulator) -> None:
    assert _levels(simulator, "schedule=60:fan:1,60:fan:0&t=120")["fan"] == 0.0
    assert _levels(simulator, "schedule=60:fan:0,60:fan:1&t=120")["fan"] == 1.0
    assert _levels(simulator, "schedule=60:fan:1&schedule=60:fan:0&t=120")["fan"] == 0.0


def test_no_daily_commands_are_not_the_scenarios_own(simulator: Simulator) -> None:
    own = _levels(simulator, f"t={MORNING_S:.0f}", "reference_greenhouse")
    none = _levels(simulator, f"t={MORNING_S:.0f}&daily=none", "reference_greenhouse")

    assert own["fan_left"] == 1.0
    assert none["fan_left"] == 0.0
    assert (
        climate_run(simulator, RunRequest("reference_greenhouse"))[0]
        != climate_run(
            simulator, RunRequest("reference_greenhouse", plan=RunPlan.requested(daily=()))
        )[0]
    )


def test_a_run_left_unsaid_is_its_scenarios_default(simulator: Simulator) -> None:
    said = RunRequest(
        "climate_box", layout=DEFAULT_LAYOUT, weather=DEFAULT_WEATHER, levels={}, openings={}
    )

    assert climate_run(simulator, RunRequest("climate_box"))[0] == climate_run(simulator, said)[0]
    assert _levels(simulator, "t=60") == _levels(
        simulator, f"layout={DEFAULT_LAYOUT}&weather={DEFAULT_WEATHER}&t=60"
    )


@pytest.mark.parametrize(("method", "route"), RUN_ROUTES)
@pytest.mark.parametrize(("query", "error"), MALFORMED.items())
def test_every_route_that_makes_a_run_refuses_a_malformed_one_alike(
    simulator: Simulator, method: str, route: str, query: str, error: str
) -> None:
    response = respond(simulator, method, f"/api/scenarios/climate_box/{route}?{query}")

    assert (response.status, response.body) == (HTTPStatus.BAD_REQUEST, {"error": error})


def test_a_checkpoints_run_is_the_run_it_was_saved_from(
    simulator: Simulator, afresh: Callable[[], None]
) -> None:
    run = RunRequest(
        "climate_box",
        levels={"heater": 1.0},
        openings={},
        plan=RunPlan.requested(commands=((600.0, "fan", 1.0), (600.0, "fan", 0.0)), daily=()),
    )
    saved = checkpoints.save_checkpoint(simulator, run, time_s=DAY_S)
    kept = checkpoints.checkpoint(simulator, saved.checkpoint_id)

    assert climate_run(simulator, kept.run())[0] == climate_run(simulator, run)[0]
    # In the checkpoint's own format, which uploads read (`CHECKPOINT_FORMAT`).
    document = json.loads(kept.model_dump_json())
    assert document["checkpoint_format"] == checkpoints.CHECKPOINT_FORMAT
    assert {name: document[name] for name in ("layout", "weather", "plan")} == {
        "layout": DEFAULT_LAYOUT,
        "weather": DEFAULT_WEATHER,
        "plan": {
            "actions": [
                {"at_s": 600.0, "action": {"kind": "set_level", "device_id": "fan", "level": 1.0}},
                {"at_s": 600.0, "action": {"kind": "set_level", "device_id": "fan", "level": 0.0}},
            ],
            "daily": [],
        },
    }


def test_a_runs_plan_is_the_protocols_actions_of_what_it_asks() -> None:
    """Each command, daily command and target change a request writes is
    the protocol's own action (P13.2): a device's level, or a heating
    target, at its moment or every day."""
    plan = RunPlan.requested(
        commands=((60.0, "fan", 1.0),),
        daily=((64800.0, "heater", 0.5),),
        targets=((3600.0, "heating_day", 24.0),),
    ).validated()

    assert plan.actions == (
        PlannedAt(at_s=60.0, action=SetLevel(device_id="fan", level=1.0)),
        PlannedAt(at_s=3600.0, action=SetTarget(target="heating_day", value_c=24.0)),
    )
    assert plan.daily == (
        PlannedDaily(time_of_day_s=64800.0, action=SetLevel(device_id="heater", level=0.5)),
    )
    # And back as the request wrote them, which name its run (decision 0042).
    assert plan.commanded() == ((60.0, "fan", 1.0),)
    assert plan.daily_commanded() == ((64800.0, "heater", 0.5),)
    assert plan.targeted() == ((3600.0, "heating_day", 24.0),)


def test_a_plan_is_checked_by_the_run_that_carries_it_out(simulator: Simulator) -> None:
    """As a request writes it, a plan is not checked; the run checks it in
    its own words, and the protocol's rules hold it once it is."""
    asked = RunPlan.requested(commands=((60.0, "fan", 2.0),))

    with pytest.raises(InvalidRequest, match="a level runs from 0 to 1: fan"):
        climate_run(simulator, RunRequest("climate_box", plan=asked))
    with pytest.raises(ValidationError):
        asked.validated()


def test_a_device_handed_back_to_its_control_loop_is_refused_until_a_run_can(
    simulator: Simulator,
) -> None:
    auto = RunPlan(
        actions=(PlannedAt(at_s=60.0, action=SetLevel(device_id="heater", level="auto")),)
    )

    with pytest.raises(InvalidRequest, match=r"does not yet hand a device back .*\(auto\)"):
        climate_run(simulator, RunRequest("climate_box", plan=auto))


@pytest.mark.parametrize("all_off", [False, True])
def test_a_format_3_checkpoint_is_read_as_its_runs_plan(
    simulator: Simulator,
    all_off: bool,
    written_in_format_3: Callable[[bool], dict[str, Any]],
) -> None:
    """The kept opening days are written in format 3: their commands, daily
    commands and target changes are read as their run's plan, which names
    the run they were saved from."""
    written = written_in_format_3(all_off)

    read = checkpoints.read_checkpoint(written)

    assert read.checkpoint_format == checkpoints.CHECKPOINT_FORMAT
    assert read.plan.commanded() == tuple(tuple(each) for each in written["commands"])
    assert read.plan.targeted() == tuple(tuple(each) for each in written["targets"])
    assert read.plan.daily_commanded() == (
        None if written["daily"] is None else tuple(tuple(each) for each in written["daily"])
    )
    saved_from = RunRequest(
        REFERENCE,
        levels=written["levels"],
        plan=RunPlan.requested(daily=None if written["daily"] is None else ()),
    )
    assert climate_run(simulator, read.run())[0] == climate_run(simulator, saved_from)[0]


@pytest.mark.parametrize(
    ("plan", "said"),
    [
        ({"commands": [[60.0, "fan"]]}, "each a moment, a name and a number"),
        ({"commands": 3}, "each a moment, a name and a number"),
        ({"commands": [{"0": 0, "fan": 0, "1": 0}]}, "each a moment, a name and a number"),
        ({"targets": [["x"]]}, "each a moment, a name and a number"),
        ({"daily": [[0.0, "fan", 1.0, "more"]]}, "each a moment, a name and a number"),
        ({"plan": {}}, "a format 3 checkpoint keeps no plan"),
        # Held to the protocol's rules as it is read, by the field at fault.
        ({"commands": [[0.0, "fan", 2.0]]}, "plan.actions.0.action.set_level.level"),
        ({"targets": [[60.0, "venting_day", 20.0]]}, "plan.actions.0.action.set_target.target"),
    ],
)
def test_a_format_3_checkpoint_whose_plan_is_not_one_is_refused(
    plan: dict[str, Any], said: str, written_in_format_3: Callable[[bool], dict[str, Any]]
) -> None:
    written = written_in_format_3(False)

    with pytest.raises(InvalidRequest, match="not a checkpoint") as refused:
        checkpoints.read_checkpoint(written | plan)
    assert said in refused.value.message


def test_a_format_3_checkpoints_plan_is_the_one_its_run_would_be_saved_with(
    simulator: Simulator,
    afresh: Callable[[], None],
    written_in_format_3: Callable[[bool], dict[str, Any]],
) -> None:
    """Commands, daily commands and target changes as format 3 wrote them
    are read as the plan a checkpoint of the same run keeps in format 4,
    which then downloads and uploads as itself."""
    commands: list[Commanded] = [(600.0, "roof_vent_1", 1.0), (600.0, "roof_vent_1", 0.5)]
    daily: list[Commanded] = [(64800.0, "fan_right", 1.0)]
    targets: list[Commanded] = [(86400.0, "heating_night", 12.0), (3600.0, "heating_day", 20.0)]
    written = written_in_format_3(False)
    as_written = {
        name: [list(each) for each in part]
        for name, part in (("commands", commands), ("daily", daily), ("targets", targets))
    }

    read = checkpoints.read_checkpoint(written | as_written)

    saved = RunPlan.requested(commands=commands, daily=daily, targets=targets).validated()
    assert read.plan == saved
    kept = checkpoints.upload_checkpoint(simulator, written | as_written)
    downloaded = json.loads(checkpoints.checkpoint(simulator, kept.checkpoint_id).model_dump_json())
    assert downloaded["checkpoint_format"] == checkpoints.CHECKPOINT_FORMAT
    assert checkpoints.upload_checkpoint(simulator, downloaded) == kept


def test_a_runs_targets_are_the_protocols() -> None:
    """A target a run changes, and the range it takes, are the protocol's
    `set_target`'s, so that a plan the run checked is one the protocol
    holds too."""
    assert {target.value for target in Target} == set(
        get_args(SetTarget.model_fields["target"].annotation)
    )
    assert SETPOINT_RANGE_C == HEATING_SETPOINT_RANGE_C


def test_a_checkpoint_in_a_format_no_simulator_wrote_names_those_it_reads() -> None:
    with pytest.raises(
        InvalidRequest, match="reads format 9, and formats 2, 3, 4, 5, 6, 7 and 8 as it"
    ):
        checkpoints.read_checkpoint({"checkpoint_format": 1})
