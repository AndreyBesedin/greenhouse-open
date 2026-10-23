"""The run a request asks for (audit W11, `AUDIT.6`), read once from its
query and taken by every service that takes a run: its identity apart from
the moment and the window, its commands in their order, same-time ones too,
no daily commands apart from its scenario's own, its defaults and errors as
they were, and a checkpoint's run the run it was saved from, in the
checkpoint's own format."""

import dataclasses
import gzip
import json
import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import Any, Final

import pytest
from greenhouse_protocol.actions import SetLevel, SetTarget
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.scenarios.manifest_files import opening_file
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.climate_readings import EquipmentAt
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.runs import PlannedAt, PlannedDaily, RunPlan, RunRequest
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
    simulator: Simulator, all_off: bool
) -> None:
    """The kept opening days are written in format 3: their commands, daily
    commands and target changes are read as their run's plan, which names
    the run they were saved from."""
    written = json.loads(gzip.decompress(opening_file(REFERENCE, all_off).read_bytes()))
    assert written["checkpoint_format"] == checkpoints.WITH_COMMANDS

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
    "plan",
    [
        {"commands": [[60.0, "fan"]]},
        {"commands": 3},
        {"targets": [["x"]]},
        {"daily": [[0.0, "fan", 1.0, "more"]]},
    ],
)
def test_a_format_3_checkpoint_whose_plan_is_not_one_is_refused(plan: dict[str, Any]) -> None:
    written = json.loads(gzip.decompress(opening_file(REFERENCE).read_bytes()))

    with pytest.raises(InvalidRequest, match="not a checkpoint"):
        checkpoints.read_checkpoint(written | plan)


def test_a_checkpoint_in_a_format_no_simulator_wrote_names_those_it_reads() -> None:
    with pytest.raises(InvalidRequest, match="reads format 4, and formats 2 and 3 as it"):
        checkpoints.read_checkpoint({"checkpoint_format": 1})
