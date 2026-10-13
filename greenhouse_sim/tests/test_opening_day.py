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
from collections.abc import Iterator
from typing import Final

import pytest

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
from greenhouse_sim.services.crop import forget_crops, run_crop
from greenhouse_sim.services.fields import climate_run, forget_climate_runs
from greenhouse_sim.services.replay import _rounded
from greenhouse_sim.services.scenarios import scenario_summaries

SCENARIO: Final = "reference_greenhouse"


@pytest.fixture(autouse=True)
def _afresh() -> Iterator[None]:
    forget_climate_runs()
    forget_crops()
    checkpoints.forget_checkpoints()
    yield
    checkpoints.forget_checkpoints()


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
    air, rounded as the replay's probes are."""
    return _rounded(checkpoint.model_dump(mode="json", include={"plants", "house", "lived"}))


def test_the_kept_opening_day_is_the_manifests_and_bears_red_fruit() -> None:
    day = opening_day(SCENARIO)
    kept = _kept()

    assert day == kept.day == 80
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
        {},
    )
    assert off.house.temperature_c < kept.house.temperature_c
    listed = next(s for s in scenario_summaries() if s.id == SCENARIO)
    assert listed.opening_day == day
    assert [s.opening_day for s in scenario_summaries() if s.id != SCENARIO] == [None] * 5


def test_kept_as_the_api_starts_the_runs_later_days_carry_on_from_it() -> None:
    assert checkpoints.load_openings() == []

    plants = run_crop(SCENARIO).plants_on(81)
    house = climate_run(SCENARIO)[1].house
    off = climate_run(SCENARIO, daily=[])[1].house
    off.air_at(80.5 * DAY_S)

    assert len(plants) == 32
    # Only the opening day's air was worked out, from its start, in the run
    # and in the same run with everything off.
    assert [m for m in house._kept if 0.0 < m < 80 * DAY_S] == []
    assert [m for m in off._kept if 0.0 < m < 80 * DAY_S] == []
    assert [c.day for c in checkpoints.checkpoints()] == [80, 80]


@pytest.mark.slow
def test_replayed_from_the_runs_start_the_opening_day_is_the_one_kept() -> None:
    kept = _kept()
    crop = run_crop(SCENARIO)

    assert all(_red(crop.plants_on(day)) == 0 for day in range(kept.day))
    saved = checkpoints.save_checkpoint(SCENARIO, time_s=kept.day * DAY_S)

    assert _state(checkpoints.checkpoint(saved.checkpoint_id)) == _state(kept)


def _update() -> None:
    crop = run_crop(SCENARIO)
    day = next(day for day in range(crop.days + 1) if _red(crop.plants_on(day)) > 0)
    path = MANIFESTS_DIR / f"{SCENARIO}.json"
    manifest = json.loads(path.read_text())
    manifest["opening_day"] = day
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    opening_file(SCENARIO).parent.mkdir(exist_ok=True)
    # The run, and the same run with everything off, which a viewer charts
    # beside it.
    for all_off, daily in ((False, None), (True, [])):
        saved = checkpoints.save_checkpoint(SCENARIO, time_s=day * DAY_S, daily=daily)
        opening_file(SCENARIO, all_off).write_bytes(
            checkpoints.opening_bytes(checkpoints.checkpoint(saved.checkpoint_id))
        )
        print(f"wrote day {day} to {opening_file(SCENARIO, all_off)}")


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_opening_day.py --update")
    _update()
