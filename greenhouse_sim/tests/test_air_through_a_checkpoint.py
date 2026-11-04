"""The air at a moment is the same array whichever way it was reached: worked
from the run's start, or from a checkpoint read as a store keeps it. Run ids,
digests and everything recorded rest on that, so it is held on a run whose plan
changes: its targets, its devices and vents moved, and a fork's own after the
moment it inherits."""

import json

import pytest
from pydantic import JsonValue

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.day import window_start
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import checkpoints, climate_readings, fields
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.fields import CLIMATE
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.simulator import Simulator

HOUR_S = 3600.0
# The day the checkpoint is of, and moments it is asked for after it: on a
# minute, between minutes, and around the plan's changes.
DAY = 1
AFTER = tuple(
    DAY * DAY_S + offset for offset in (60.0, 90.5, 4 * HOUR_S, 7 * HOUR_S + 30.0, 12 * HOUR_S)
)

# Before the checkpoint, so that it keeps them; and after it, so that a run
# restored has to carry them out from it.
_MOVED = (
    (0.4 * DAY_S, "fan_left", 1.0),
    (0.6 * DAY_S, "roof_vent_1", 0.25),
    (DAY * DAY_S + 2 * HOUR_S, "roof_vent_1", 0.75),
    (DAY * DAY_S + 5 * HOUR_S, "fan_left", 0.0),
)
_TARGETED = (
    (0.5 * DAY_S, "heating_night", 16.0),
    (DAY * DAY_S + 3 * HOUR_S, "heating_day", 18.0),
)
_CHANGING = RunPlan.requested(commands=_MOVED, targets=_TARGETED)
# A fork of that run: the same up to the checkpoint, its own after it.
_FORKED = RunPlan.requested(
    commands=(*_MOVED, (DAY * DAY_S + HOUR_S, "roof_vent_2", 1.0)),
    targets=(*_TARGETED, (DAY * DAY_S + 6 * HOUR_S, "heating_day", 15.0)),
)
_PARENTS = {"own": RunPlan(), "changing": _CHANGING, "fork": _CHANGING}
_PLANS = {"own": RunPlan(), "changing": _CHANGING, "fork": _FORKED}


def _checkpoint_as_a_store_keeps_it(scenario_id: str, parent: RunPlan) -> JsonValue:
    """The checkpoint a worker of the parent run would write at the day's start,
    through the JSON it is kept in."""
    with Simulator() as worker:
        made = checkpoints.make_checkpoint(
            worker, RunRequest(scenario_id, plan=parent), DAY * DAY_S
        )
    document: JsonValue = json.loads(made.model_dump_json())
    return document


def _air_at(simulator: Simulator, run: RunRequest, time_s: float) -> dict[str, object]:
    """All a page reads of the air at a moment, each to the last bit: arrays
    published as they are held."""
    return {
        "field": fields.field(simulator, run, CLIMATE, time_s).model_dump(),
        "house": climate_readings.house_air(simulator, run, time_s).model_dump(),
        "its own": climate_readings.house_air(simulator, run, time_s, all_off=False).controlled,
        "at": climate_readings.house_air_at(simulator, run, time_s),
        "glazing": climate_readings.glazing(simulator, run, time_s).model_dump(),
        "openings": climate_readings.openings(simulator, run, time_s).model_dump(),
        "equipment": climate_readings.equipment_at(simulator, run, time_s).model_dump(),
    }


@pytest.mark.slow
@pytest.mark.parametrize("plan", list(_PLANS))
@pytest.mark.parametrize("scenario_id", ["tomgro_house", "reference_greenhouse"])
def test_the_air_through_a_checkpoint_is_the_air_from_the_start(
    scenario_id: str, plan: str
) -> None:
    run = RunRequest(scenario_id, plan=_PLANS[plan])
    document = _checkpoint_as_a_store_keeps_it(scenario_id, _PARENTS[plan])
    with Simulator() as from_the_start, Simulator() as restored:
        checkpoints.upload_checkpoint(restored, document)
        house = climate_run(restored, run)[1].house
        for moment in AFTER:
            assert _air_at(restored, run, moment) == _air_at(from_the_start, run, moment), moment
        # It was reached through the checkpoint: nothing before the moment it
        # keeps the air at was worked out.
        earliest = window_start(DAY * DAY_S)
        assert [m for m in house._moments if 0.0 < m < earliest] == []
        # The checkpoint's own moment charts the day it ends, before the checkpoint.
        moment = DAY * DAY_S
        assert _air_at(restored, run, moment) == _air_at(from_the_start, run, moment)


def test_the_run_all_off_is_worked_out_only_when_it_is_asked_for() -> None:
    path = "/api/scenarios/climate_box/climate/house?t=600"
    with Simulator() as simulator:
        without = respond(simulator, "GET", f"{path}&all_off=0").body
        assert isinstance(without, dict)
        assert without["all_off"] is None
        assert len(simulator.climate_runs.values()) == 1

        whole = respond(simulator, "GET", path).body
        assert isinstance(whole, dict)
        assert whole["all_off"] is not None
        assert whole["controlled"] == without["controlled"]
        assert whole["times_s"] == without["times_s"]
