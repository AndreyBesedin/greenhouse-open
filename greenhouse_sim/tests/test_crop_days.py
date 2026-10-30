"""Every run's crop keeps its days alike, whatever grows it (P14.8, decision
0062): a crop made of no plants at all, a count of the days it lived, keeps
them as a crop of plants does."""

from collections.abc import Sequence
from typing import Final

import pytest

from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.core.crop_days import CropDays, DayWork

DAYS: Final = 10


class _Counted:
    """A crop that is the sum of the days it lived, each day's worth its
    number, counting the days it was asked to work out."""

    made_of = "counts"

    def __init__(self) -> None:
        self.lived_asked: list[int] = []

    def first(self) -> int:
        return 0

    def lived(self, day: int, state: int) -> int:
        self.lived_asked.append(day)
        return day

    def next_day(
        self, day: int, state: int, lived: int, planned: Sequence[CropAction]
    ) -> tuple[int, DayWork | None]:
        return state + lived, (DayWork((), {}) if planned else None)

    def read(self, state: object) -> int | None:
        return state if isinstance(state, int) else None


def _days() -> tuple[CropDays[int, int], _Counted]:
    growth = _Counted()
    return CropDays(growth, days=DAYS, planned={}), growth


def test_a_crop_of_no_plants_lives_its_days_in_order_once() -> None:
    crop, growth = _days()

    assert crop.on(5) == sum(range(5))
    assert crop.on(3) == sum(range(3))
    assert crop.lived_on(4) == 4
    assert growth.lived_asked == list(range(5))
    with pytest.raises(ValueError, match="days 0 to 10, not 11"):
        crop.on(11)


def test_a_crop_of_no_plants_carries_on_from_another_and_from_a_checkpoint() -> None:
    source, _ = _days()
    source.on(6)
    branch, asked = _days()
    branch.carry_on_from(source, 6)

    assert branch.on(6) == source.on(6)
    assert asked.lived_asked == []

    seeded, asked = _days()
    seeded.seed(4, source.on(4), [source.lived_on(day) for day in range(4)])
    assert seeded.on(6) == source.on(6)
    assert asked.lived_asked == [4, 5]
    with pytest.raises(ValueError, match="a crop of counts takes no others"):
        _days()[0].seed(0, "not a count", [])
