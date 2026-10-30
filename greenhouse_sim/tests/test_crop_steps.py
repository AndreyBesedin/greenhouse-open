"""Every run's crop keeps its steps alike, whatever grows it (P14.8, P16.1,
decisions 0062 and 0064): a crop made of no plants at all, a count of the
steps it lived, keeps them as a crop of plants keeps its days, at whatever
step divides a day."""

from collections.abc import Sequence
from typing import Final

import pytest

from greenhouse_sim.core.clock import steps_a_day
from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.core.crop_steps import CropSteps, StepWork
from greenhouse_sim.units import DAY_S, HOUR_S, HOURS_A_DAY

DAYS: Final = 10


class _Counted:
    """A crop that is the sum of the steps it lived, each step's worth its
    number, counting the steps it was asked to work out."""

    made_of = "counts"

    def __init__(self, step_s: float = DAY_S) -> None:
        self.step_s = step_s
        self.lived_asked: list[int] = []

    def first(self) -> int:
        return 0

    def lived(self, step: int, state: int) -> int:
        self.lived_asked.append(step)
        return step

    def next_step(
        self, step: int, state: int, lived: int, planned: Sequence[CropAction]
    ) -> tuple[int, StepWork | None]:
        return state + lived, (StepWork((), {}) if planned else None)

    def read(self, state: object, lived: Sequence[object]) -> tuple[int, list[int]] | None:
        steps = [step for step in lived if isinstance(step, int)]
        if not isinstance(state, int) or len(steps) != len(lived):
            return None
        return state, steps


def _steps(step_s: float = DAY_S, steps: int = DAYS) -> tuple[CropSteps[int, int], _Counted]:
    growth = _Counted(step_s)
    return CropSteps(growth, steps=steps, planned={}), growth


def test_a_crop_of_no_plants_lives_its_steps_in_order_once() -> None:
    crop, growth = _steps()

    assert crop.on(5) == sum(range(5))
    assert crop.on(3) == sum(range(3))
    assert crop.lived_on(4) == 4
    assert growth.lived_asked == list(range(5))
    with pytest.raises(ValueError, match="days 0 to 10, not 11"):
        crop.on(11)


def test_a_crop_of_no_plants_carries_on_from_another_and_from_a_checkpoint() -> None:
    source, _ = _steps()
    source.on(6)
    branch, asked = _steps()
    branch.carry_on_from(source, 6)

    assert branch.on(6) == source.on(6)
    assert asked.lived_asked == []

    seeded, asked = _steps()
    seeded.seed(4, source.on(4), [source.lived_on(step) for step in range(4)])
    assert seeded.on(6) == source.on(6)
    assert asked.lived_asked == [4, 5]
    with pytest.raises(ValueError, match="a crop of counts takes no others"):
        _steps()[0].seed(0, "not a count", [])


def test_a_crop_of_an_hours_step_keeps_its_hours_and_meets_each_midnight() -> None:
    crop, growth = _steps(HOUR_S, 2 * HOURS_A_DAY)

    assert crop.steps_a_day == HOURS_A_DAY
    assert crop.on(HOURS_A_DAY) == sum(range(HOURS_A_DAY))
    assert growth.lived_asked == list(range(HOURS_A_DAY))
    with pytest.raises(ValueError, match="steps of 3600 s 0 to 48, not 49"):
        crop.on(2 * HOURS_A_DAY + 1)


def test_the_crop_at_a_moment_is_the_same_whoever_asks_when() -> None:
    """Decision 0064: between two of its steps a crop is as at the earlier,
    and its steps are worked out on their grid alone, so asking for it at
    any moments, in any order and as often as anyone likes, never changes
    it."""
    asked, _ = _steps(HOUR_S, 2 * HOURS_A_DAY)
    moments = [9 * HOUR_S, 9.5 * HOUR_S, 10 * HOUR_S, 9 * HOUR_S, 30.25 * HOUR_S, 10 * HOUR_S]

    seen = [asked.at(moment) for moment in moments]

    assert seen == [sum(range(int(moment // HOUR_S))) for moment in moments]
    nobody, _ = _steps(HOUR_S, 2 * HOURS_A_DAY)
    assert asked.at(2 * DAY_S) == nobody.at(2 * DAY_S)


@pytest.mark.parametrize("step_s", [7 * HOUR_S, 0.0, -HOUR_S, 2 * DAY_S])
def test_a_step_that_does_not_divide_a_day_is_refused(step_s: float) -> None:
    with pytest.raises(ValueError, match="a crop's step divides a day"):
        _steps(step_s)


@pytest.mark.parametrize(
    ("step_s", "count"), [(DAY_S, 1), (HOUR_S, HOURS_A_DAY), (HOUR_S / 4, 4 * HOURS_A_DAY)]
)
def test_a_day_holds_a_whole_number_of_steps(step_s: float, count: int) -> None:
    assert steps_a_day(step_s) == count
