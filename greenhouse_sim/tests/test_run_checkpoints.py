"""A run's checkpoints (P09.5): its state at a day's start, kept in the API's
memory, downloaded and uploaded as JSON; a restored run carrying on as the
original does, and a branch sharing every day before its own."""

import json
import math
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.manifest_files import manifest_digest
from greenhouse_sim.services import checkpoints, kept_states
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.crop import run_crop
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

PLANT = "reference_greenhouse_plant_001"
HOUR_S = 3600.0
# The reference run's heater, off an hour into its second day: a branch.
BRANCH = ((DAY_S + HOUR_S, "heater", 0.0),)


# Each test starts with no run, crop or checkpoint kept, as after the API
# restarts.
pytestmark = pytest.mark.usefixtures("afresh")


def _restarted(simulator: Simulator, afresh: Callable[[], None]) -> None:
    """As after the API restarts, its checkpoints uploaded again, as a client
    that downloaded them keeps them: no run or crop kept."""
    documents = [
        checkpoints.checkpoint(simulator, summary.checkpoint_id).model_dump(mode="json")
        for summary in checkpoints.checkpoints(simulator)
    ]
    afresh()
    for document in documents:
        checkpoints.upload_checkpoint(simulator, document)


def _body(simulator: Simulator, method: str, path: str, body: bytes = b"") -> Any:
    response = respond(simulator, method, path, body)
    assert response.status == HTTPStatus.OK, response.body
    return response.body


def test_a_checkpoint_keeps_a_runs_state_at_the_start_of_its_day(simulator: Simulator) -> None:
    saved = checkpoints.save_checkpoint(
        simulator, RunRequest("reference_greenhouse"), time_s=1.5 * DAY_S
    )
    kept = checkpoints.checkpoint(simulator, saved.checkpoint_id)
    _, climate = climate_run(simulator, RunRequest("reference_greenhouse"))
    crop = run_crop(simulator, RunRequest("reference_greenhouse"))

    assert (saved.day, saved.time_s, saved.plants) == (1, DAY_S, 32)
    assert kept.house == climate.house.air_at(DAY_S)
    # And an hour before its day, where its first hour's field starts.
    assert kept.house_before == climate.house.air_at(DAY_S - HOUR_S)
    assert kept.plants == list(crop.plants_on(1))
    assert kept.lived == crop.lived_through(1)
    assert kept.manifest == manifest_digest("reference_greenhouse")
    assert (kept.layout, kept.weather, kept.daily) == ("default", "default", None)
    assert checkpoints.checkpoints(simulator) == [saved]


def test_it_keeps_the_commands_given_before_its_day_and_its_daily_ones(
    simulator: Simulator,
) -> None:
    saved = checkpoints.save_checkpoint(
        simulator,
        RunRequest(
            "climate_box",
            levels={"fan": 1.0},
            commands=((600.0, "heater", 1.0), (DAY_S + 600.0, "heater", 0.0)),
            daily=((64800.0, "heater", 1.0),),
        ),
        time_s=DAY_S + 60.0,
    )

    # The climate box grows the simple model: no plants are kept.
    assert saved.plants == 0
    assert saved.commands == [(600.0, "heater", 1.0)]
    assert saved.daily == [(64800.0, "heater", 1.0)]
    assert saved.levels == {"fan": 1.0}


def test_a_restored_run_carries_on_as_the_original_does(
    simulator: Simulator, afresh: Callable[[], None]
) -> None:
    later = f"/api/scenarios/reference_greenhouse/crop/{PLANT}?t={2 * DAY_S:.0f}"
    original = _body(simulator, "GET", later)
    original_air = climate_run(simulator, RunRequest("reference_greenhouse"))[1].house.air_at(
        2 * DAY_S + HOUR_S
    )
    checkpoints.save_checkpoint(simulator, RunRequest("reference_greenhouse"), time_s=DAY_S)

    _restarted(simulator, afresh)
    restored = _body(simulator, "GET", later)
    house = climate_run(simulator, RunRequest("reference_greenhouse"))[1].house

    assert restored == original
    assert house.air_at(2 * DAY_S + HOUR_S) == pytest.approx(original_air)
    # It took the checkpoint's first day over, and worked out no moment of it.
    assert [m for m in house._kept if 0.0 < m < DAY_S - HOUR_S] == []


def test_a_restored_run_draws_its_days_first_hour_from_the_checkpoint(
    simulator: Simulator,
    afresh: Callable[[], None],
) -> None:
    first_hour = DAY_S + 20 * 60.0
    original = _body(
        simulator, "GET", f"/api/scenarios/reference_greenhouse/fields/climate?t={first_hour:.0f}"
    )
    checkpoints.save_checkpoint(simulator, RunRequest("reference_greenhouse"), time_s=DAY_S)

    _restarted(simulator, afresh)
    restored = _body(
        simulator, "GET", f"/api/scenarios/reference_greenhouse/fields/climate?t={first_hour:.0f}"
    )
    house = climate_run(simulator, RunRequest("reference_greenhouse"))[1].house

    # Its grid run starts an hour before the day began, from the air the
    # checkpoint kept then: none of the day before is worked out.
    assert restored == original
    assert [m for m in house._kept if 0.0 < m < DAY_S - HOUR_S] == []


def test_a_checkpoint_on_a_runs_first_day_keeps_no_earlier_air(simulator: Simulator) -> None:
    saved = checkpoints.save_checkpoint(simulator, RunRequest("climate_box"), time_s=600.0)

    assert checkpoints.checkpoint(simulator, saved.checkpoint_id).house_before is None


def test_a_branch_shares_every_day_before_its_own(
    simulator: Simulator, afresh: Callable[[], None]
) -> None:
    checkpoints.save_checkpoint(simulator, RunRequest("reference_greenhouse"), time_s=DAY_S)
    trunk = run_crop(simulator, RunRequest("reference_greenhouse"))
    trunk_days = trunk.environments(PLANT, 2)

    _restarted(simulator, afresh)
    branch = run_crop(simulator, RunRequest("reference_greenhouse", commands=BRANCH))
    house = climate_run(simulator, RunRequest("reference_greenhouse", commands=BRANCH))[1].house
    branch_days = branch.environments(PLANT, 2)

    assert branch_days[0] == trunk_days[0]
    # Its heater off from an hour into the second day, it lives that day
    # colder.
    assert branch_days[1].mean_temperature_c < trunk_days[1].mean_temperature_c - 1.0
    assert [m for m in house._kept if 0.0 < m < DAY_S - HOUR_S] == []
    # A run that differs before the checkpoint's day takes nothing over.
    other = run_crop(
        simulator, RunRequest("reference_greenhouse", commands=((HOUR_S, "heater", 1.0),))
    )
    assert other.environments(PLANT, 1)[0] != trunk_days[0]


def test_the_opening_days_are_kept_beside_the_last_checkpoints_saved(simulator: Simulator) -> None:
    # The openings, kept as the API starts, are the oldest checkpoints: the
    # next saves do not evict them.
    assert checkpoints.load_openings(simulator) == []
    openings = {summary.checkpoint_id for summary in checkpoints.checkpoints(simulator)}
    for level in range(checkpoints.KEPT_CHECKPOINTS + 1):
        checkpoints.save_checkpoint(
            simulator, RunRequest("climate_box", levels={"heater": level / 100})
        )

    kept = {summary.checkpoint_id for summary in checkpoints.checkpoints(simulator)}
    assert openings
    assert openings <= kept
    assert len(kept - openings) == checkpoints.KEPT_CHECKPOINTS


def test_a_checkpoint_downloads_and_uploads_as_it_was(
    simulator: Simulator, afresh: Callable[[], None]
) -> None:
    saved = _body(
        simulator, "POST", f"/api/scenarios/reference_greenhouse/checkpoints?t={DAY_S:.0f}"
    )
    downloaded = _body(simulator, "GET", f"/api/checkpoints/{saved['checkpoint_id']}")
    listed = _body(simulator, "GET", "/api/checkpoints")

    afresh()
    assert respond(simulator, "GET", "/api/checkpoints").body == []
    uploaded = _body(simulator, "POST", "/api/checkpoints", json.dumps(downloaded).encode())

    assert uploaded == saved
    assert listed == [saved]
    assert _body(simulator, "GET", "/api/checkpoints") == [saved]


def _refusal(simulator: Simulator, document: Any) -> str:
    response = respond(simulator, "POST", "/api/checkpoints", json.dumps(document).encode())
    assert response.status == HTTPStatus.BAD_REQUEST
    assert isinstance(response.body, dict)
    return str(response.body["error"])


def test_a_checkpoint_no_run_could_reach_is_refused(simulator: Simulator) -> None:
    saved = checkpoints.save_checkpoint(
        simulator, RunRequest("reference_greenhouse"), time_s=2 * DAY_S
    )
    good = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
    house = good["house"]
    plant = good["plants"][0]

    assert "-300 °C" in _refusal(simulator, good | {"house": house | {"temperature_c": -300.0}})
    assert "g/kg of water" in _refusal(simulator, good | {"house": house | {"humidity_g_kg": -5.0}})
    assert "ppm of CO₂" in _refusal(simulator, good | {"house": house | {"co2_ppm": 1e300}})
    assert "before it" in _refusal(simulator, good | {"house_before": house | {"co2_ppm": -1.0}})
    # A plant older than the days it lived, as a later day's crop with its
    # days cut to fit an earlier one's would be.
    older = plant | {"thermal_time": plant["thermal_time"] + 50.0}
    assert "add up to" in _refusal(simulator, good | {"plants": [older, *good["plants"][1:]]})
    # Numbers JSON has none for reach the service from Python only.
    hot = [
        {plant_id: day[plant_id] | {"mean_temperature_c": math.inf} for plant_id in day}
        for day in good["lived"]
    ]
    for unreachable in (
        good | {"house": house | {"temperature_c": math.nan}},
        good | {"lived": hot},
    ):
        with pytest.raises(InvalidRequest, match="not finite"):
            checkpoints.upload_checkpoint(simulator, unreachable)


def test_a_clean_slate_forgets_the_runs_that_took_a_checkpoints_state(
    simulator: Simulator,
    afresh: Callable[[], None],
) -> None:
    checkpoints.save_checkpoint(simulator, RunRequest("reference_greenhouse"), time_s=DAY_S)
    _restarted(simulator, afresh)
    seeded = climate_run(simulator, RunRequest("reference_greenhouse"))[1]

    afresh()

    assert climate_run(simulator, RunRequest("reference_greenhouse"))[1] is not seeded


def test_a_checkpoint_that_does_not_fit_its_run_is_refused(simulator: Simulator) -> None:
    saved = checkpoints.save_checkpoint(simulator, RunRequest("reference_greenhouse"), time_s=DAY_S)
    good = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")

    assert "another version" in _refusal(simulator, good | {"manifest": "0" * 16})
    assert "format 1" in _refusal(simulator, good | {"checkpoint_format": 1})
    assert "an hour before its day" in _refusal(simulator, good | {"house_before": None})
    assert "plants are reference_greenhouse's" in _refusal(
        simulator, good | {"plants": good["plants"][1:]}
    )
    assert "lived 1 days" in _refusal(simulator, good | {"lived": []})
    assert "days 0 to 120" in _refusal(simulator, good | {"day": 121})
    assert "has no equipment 'boiler'" in _refusal(simulator, good | {"levels": {"boiler": 1.0}})
    assert "not a checkpoint" in _refusal(simulator, {"checkpoint_format": 2})
    garbled = respond(simulator, "POST", "/api/checkpoints", b"{")
    assert (garbled.status, garbled.body) == (
        HTTPStatus.BAD_REQUEST,
        {"error": "the body is not JSON"},
    )
    missing = respond(simulator, "GET", "/api/checkpoints/nothing")
    assert missing.status == HTTPStatus.NOT_FOUND


def test_a_checkpoint_let_go_takes_its_own_state_not_one_kept_since(simulator: Simulator) -> None:
    # Codex's review of #253: a checkpoint the store lets go lets its state
    # go once the store's lock is released. Uploaded again meanwhile, the
    # same checkpoint keeps a state of its own, which that late drop must
    # leave, or a run restored from it would work its days out again.
    saved = checkpoints.save_checkpoint(simulator, RunRequest("climate_box"), time_s=DAY_S)
    document = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
    first = simulator.states.get(saved.checkpoint_id)
    checkpoints.upload_checkpoint(simulator, document)
    again = simulator.states.get(saved.checkpoint_id)
    assert first is not None and again is not None and again is not first

    kept_states.drop(simulator, saved.checkpoint_id, first)

    assert simulator.states.get(saved.checkpoint_id) is again
    assert saved in checkpoints.checkpoints(simulator)
