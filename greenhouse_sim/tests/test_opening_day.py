"""The reference run's kept opening day (P09.5): the first day with red
fruit, kept beside its manifest as a checkpoint, gzipped, which the API
keeps as it starts, so that the run's later days carry on from it; and,
replayed from the run's start, the same day.

When a deliberate change moves the reference run, write its opening day
again from `greenhouse_sim/` (about six minutes):

    python tests/test_opening_day.py --update

which finds the first day with red fruit, names it in the manifest, and
writes beside it the run's checkpoint and the same run's with everything
off, which a viewer charts beside it.
"""

import gzip
import json
import sys
from http import HTTPStatus
from itertools import pairwise
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.plant.organs import Fruit
from greenhouse_sim.biology.tomato.organ.fruit import Maturity, maturity
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.organs import FruitStage
from greenhouse_sim.scenarios.manifest_files import (
    MANIFESTS_DIR,
    manifest_digest,
    opening_day,
    opening_file,
)
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.crop import run_crop
from greenhouse_sim.services.fields import climate_run, field, off_levels
from greenhouse_sim.services.replay import _rounded
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario_summaries
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

SCENARIO: Final = "reference_greenhouse"
# Its crop near its opening day is some 12,000 organs' entities; without a
# day's crop, the scene draws its transplants in its place, some 3,000.
WHOLE_CROP_ENTITIES: Final = 10_000
# How much of a day's crop the next keeps at least, before any harvest.
KEPT_SHARE: Final = 0.95
# Its first day with red fruit, under its season and its thermostat (P10.3).
OPENING: Final = 86


# Each from a clean slate: nothing another test kept gives the run its days.
pytestmark = pytest.mark.usefixtures("afresh")


def _kept(all_off: bool = False) -> checkpoints.Checkpoint:
    return checkpoints.Checkpoint.model_validate(
        json.loads(gzip.decompress(opening_file(SCENARIO, all_off).read_bytes()))
    )


def _red(plants: tuple[Plant, ...] | list[Plant]) -> int:
    return sum(
        1
        for plant in plants
        for _, _, _, organ in plant.organs()
        if isinstance(organ, Fruit)
        and organ.stage == FruitStage.ATTACHED
        and maturity(organ.ripeness) == Maturity.RED
    )


def _state(checkpoint: checkpoints.Checkpoint) -> object:
    """What a replay compares of a checkpoint: its plants and its house's
    air, at its day's start and an hour before, rounded as the replay's
    probes are."""
    return _rounded(
        checkpoint.model_dump(mode="json", include={"plants", "house", "house_before", "lived"})
    )


def test_the_kept_opening_day_is_the_manifests_and_bears_red_fruit() -> None:
    day = opening_day(SCENARIO)
    kept = _kept()

    assert day == kept.day == OPENING
    assert kept.manifest == manifest_digest(SCENARIO), (
        "the reference scenario's manifest has changed: write its opening day again with "
        "`python tests/test_opening_day.py --update`"
    )
    assert _red(kept.plants) > 0
    # Beside it, the same run with everything off, as a viewer charts it.
    off = _kept(all_off=True)
    assert (off.day, off.manifest, off.daily, off.commands, off.levels) == (
        day,
        kept.manifest,
        [],
        [],
        off_levels(SCENARIO),
    )
    assert off.house.temperature_c < kept.house.temperature_c
    listed = next(s for s in scenario_summaries() if s.id == SCENARIO)
    assert listed.opening_day == day
    assert [s.opening_day for s in scenario_summaries() if s.id != SCENARIO] == [None] * 5


def test_kept_as_the_api_starts_the_runs_later_days_carry_on_from_it(simulator: Simulator) -> None:
    assert checkpoints.load_openings(simulator) == []

    plants = run_crop(simulator, RunRequest(SCENARIO)).plants_on(OPENING + 1)
    house = climate_run(simulator, RunRequest(SCENARIO))[1].house
    off = climate_run(simulator, RunRequest(SCENARIO, levels=off_levels(SCENARIO), daily=()))[
        1
    ].house
    off.air_at((OPENING + 0.5) * DAY_S)
    # The air cell by cell in the day's first hour, its grid run started an
    # hour before the day began.
    field(simulator, RunRequest(SCENARIO), "climate", time_s=OPENING * DAY_S + 20 * 60.0)

    assert len(plants) == 32
    # Only the opening day's air was worked out, from its start, in the run
    # and in the same run with everything off; before it, only the hour
    # before the day, from the air the checkpoint kept then: the grid run of
    # the day's first hour starts there, and follows the thermostat, which
    # decides by the house's air.
    hour_before = OPENING * DAY_S - HOUR_S
    before = [m for m in house._kept if 0.0 < m < OPENING * DAY_S]
    assert min(before) == hour_before
    assert [m for m in off._kept if 0.0 < m < OPENING * DAY_S] == [hour_before]
    assert [c.day for c in checkpoints.checkpoints(simulator)] == [OPENING, OPENING]


def test_the_crop_stays_whole_through_the_days_about_its_opening(simulator: Simulator) -> None:
    # The crop the viewer draws on the days the QA steps through (#197): each
    # whole, its 32 plants' organs, none fewer than the day before's by more
    # than a little, before the first harvest (day 91), and the opening day's
    # as the days either side of it.
    assert checkpoints.load_openings(simulator) == []
    entities = []
    for day in (83, 85, OPENING, OPENING + 1):
        answer = respond(
            simulator, "GET", f"/api/scenarios/{SCENARIO}/crop?t={day * DAY_S + 600:.0f}"
        )
        assert answer.status == HTTPStatus.OK, answer.body
        assert isinstance(answer.body, dict)
        crop: dict[str, Any] = answer.body
        assert crop["simulated_day"] == day
        organs = crop["entities"]
        assert {e["properties"]["plant_id"] for e in organs} == {
            f"{SCENARIO}_plant_{n:03d}" for n in range(1, 33)
        }
        entities.append(len(organs))

    assert min(entities) > WHOLE_CROP_ENTITIES
    assert all(later >= KEPT_SHARE * earlier for earlier, later in pairwise(entities))


@pytest.mark.slow
def test_replayed_from_the_runs_start_the_opening_day_is_the_one_kept(simulator: Simulator) -> None:
    kept = _kept()
    crop = run_crop(simulator, RunRequest(SCENARIO))

    assert all(_red(crop.plants_on(day)) == 0 for day in range(kept.day))
    saved = checkpoints.save_checkpoint(simulator, RunRequest(SCENARIO), time_s=kept.day * DAY_S)

    assert _state(checkpoints.checkpoint(simulator, saved.checkpoint_id)) == _state(kept)


def _update(simulator: Simulator) -> None:
    crop = run_crop(simulator, RunRequest(SCENARIO))
    day = next(day for day in range(crop.days + 1) if _red(crop.plants_on(day)) > 0)
    path = MANIFESTS_DIR / f"{SCENARIO}.json"
    manifest = json.loads(path.read_text())
    manifest["opening_day"] = day
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    opening_file(SCENARIO).parent.mkdir(exist_ok=True)
    # The run, and the same run with everything off, which a viewer charts
    # beside it: its thermostat's heater too.
    for all_off, levels, daily in ((False, {}, None), (True, off_levels(SCENARIO), ())):
        saved = checkpoints.save_checkpoint(
            simulator, RunRequest(SCENARIO, levels=levels, daily=daily), time_s=day * DAY_S
        )
        opening_file(SCENARIO, all_off).write_bytes(
            checkpoints.opening_bytes(checkpoints.checkpoint(simulator, saved.checkpoint_id))
        )
        print(f"wrote day {day} to {opening_file(SCENARIO, all_off)}")


if __name__ == "__main__":
    with Simulator() as simulator:
        if sys.argv[1:] != ["--update"]:
            raise SystemExit("usage: python tests/test_opening_day.py --update")
        _update(simulator)
