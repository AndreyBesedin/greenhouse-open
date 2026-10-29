"""The days of a run's crop, however its model grows it (P14.8, decision
0062): what every crop of the run keeps and works out alike, whatever it
is made of.

A crop's growth (`Growth`) says what it is made of and how it lives a day:
its state on the run's first day; what it experienced on a day, worked out
from the run's air and light; and its state the next day, once it has lived
that one, after the next day's crop work and its own crop actions. A crop
grown plant by plant is one (`greenhouse_sim.core.crop.PlantGrowth`).
`CropDays` keeps the rest:

- **its days in order:** the crop on day `d` has lived the run's first `d`
  days, and what it experienced on each day is kept, so that its days can
  be listed and its state on any day lived again from them, without the air
  or the light;
- **a few days' states:** its first day's, the latest worked out's, and
  the few last asked for (`KEPT_DAYS`);
- **what its own crop actions did,** day by day (`DayWork`);
- **its days taken over** from another crop of the same run, up to the
  first on which their air or their own crop actions differ
  (`carry_on_from`), and its state on a day given from a checkpoint
  (`seed`);
- **one request at a time** working it on, the others waiting for it and
  finding what it kept, and a crop carrying on from this one waiting for
  the days a request is working through rather than living them beside it.
"""

import threading
import weakref
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from greenhouse_sim.climate.run import LOOK_AGAIN_S
from greenhouse_sim.core.crop_actions import CropAction, CropEffect

# How many days' states a crop keeps besides its first day's and its
# latest's: the last asked for.
KEPT_DAYS: Final = 2


@dataclass(frozen=True)
class CropDone:
    """What one of a run's own crop actions did, or why it was refused."""

    effect: CropEffect | None = None
    refusal: str | None = None


@dataclass(frozen=True)
class DayWork:
    """A day's own crop actions as the crop carried them out: what each did,
    in the order planned; and how long the history of each plant they act
    on was once that day's crop work was done, before them."""

    done: tuple[CropDone, ...]
    work_ends: Mapping[str, int]


class Growth[StateT, LivedT](Protocol):
    """How a run's crop is made and lives its days: see the module. A
    growth keeps nothing of the days it works out; `CropDays` keeps them."""

    def first(self) -> StateT:
        """The crop on the run's first day."""
        ...

    def lived(self, day: int, state: StateT) -> LivedT:
        """What the crop, `state` on the run's day `day`, experienced on that
        day."""
        ...

    def next_day(
        self, day: int, state: StateT, lived: LivedT, planned: Sequence[CropAction]
    ) -> tuple[StateT, DayWork | None]:
        """The crop on the run's day after `day`, `state` on it: once it has
        lived it as `lived`, after the next day's crop work and then the
        run's own crop actions `planned` for it, in their order; and what
        those did, if there were any."""
        ...

    @property
    def made_of(self) -> str:
        """What the crop is made of, as a refusal names it."""
        ...

    def read(self, state: object, lived: Sequence[object]) -> tuple[StateT, list[LivedT]] | None:
        """`state` as a state of this crop, and `lived` as what it
        experienced on each day before, as a checkpoint gives them back;
        None if they are not this crop's."""
        ...


class CropDays[StateT, LivedT]:
    """A run's crop through its `days`, made and lived as `growth` says, and
    worked as the run's own crop actions on each day ask (`planned`, by
    day): see the module."""

    def __init__(
        self,
        growth: Growth[StateT, LivedT],
        *,
        days: int,
        planned: Mapping[int, tuple[CropAction, ...]],
    ) -> None:
        self.days = days
        self.growth = growth
        self._planned = dict(planned)
        # What the planned crop actions of each day worked out did.
        self._done: dict[int, DayWork] = {}
        # What the crop experienced on each day worked out, from the first.
        self._lived: list[LivedT] = []
        # The crop on the days kept: the first, the latest worked out, and
        # the last asked for.
        self._kept: OrderedDict[int, StateT] = OrderedDict({0: growth.first()})
        # One request at a time works a crop on; others wait for it, and
        # find what it kept.
        self._working = threading.RLock()
        # Held only to change what is kept, or to copy it: another crop
        # carrying on from this one copies it without waiting for a request
        # working this crop on.
        self._keeping = threading.Lock()
        # The days a request is working the crop through, from the latest
        # kept before the one asked for to it, or None: a crop carrying on
        # from this one waits while they cover what it needs, rather than
        # live them beside this crop. Told under `_keeping`, and
        # `_kept_changed` is notified when they end.
        self._stretch: tuple[int, int] | None = None
        self._kept_changed = threading.Condition(self._keeping)
        # The crops this one carries on from (`carry_on_from`), each with the
        # days through which it is the same crop: what they work out of
        # those days is taken over again whenever this crop works a day on,
        # so that a request working one of them on is neither waited for nor
        # repeated. Held weakly: a crop the kept runs have forgotten is not
        # kept alive by those that carried on from it.
        self._sources: list[tuple[weakref.ref[CropDays[StateT, LivedT]], int]] = []

    def checked(self, day: int, last: int) -> None:
        """Refused, naming its days, if `day` is not from 0 to `last`."""
        if not 0 <= day <= last:
            raise ValueError(f"a run's crop has days 0 to {last}, not {day}")

    def on(self, day: int) -> StateT:
        """The crop on the run's day `day`, from 0 to its days: once it has
        lived the days before it, after that day's crop work."""
        self.checked(day, self.days)
        with self._working:
            kept = self._kept.get(day)
            if kept is not None:
                with self._keeping:
                    self._kept.move_to_end(day)
                return kept
            self._take_over(day)
            start = max(kept_day for kept_day in self._kept if kept_day <= day)
            with self._keeping:
                self._stretch = (start, day)
            try:
                state = self._lived_through(start, day)
            finally:
                with self._kept_changed:
                    self._stretch = None
                    self._kept_changed.notify_all()
            self._keep(day, state)
            return state

    def _lived_through(self, start: int, day: int) -> StateT:
        state = self._kept[start]
        for lived in range(start, day):
            state = self._next_day(lived, state)
        return state

    def _next_day(self, lived: int, state: StateT) -> StateT:
        """The crop on the day after `lived`, `state` on it: once it has
        lived it, after the next day's crop work and its own crop actions."""
        state, work = self.growth.next_day(
            lived, state, self._day(lived, state), self._planned.get(lived + 1, ())
        )
        if work is not None:
            with self._keeping:
                self._done[lived + 1] = work
        return state

    def worked_on(self, day: int) -> DayWork | None:
        """What the run's own crop actions on its day `day` did, from 0 to
        its days, the crop worked through that day if it has not been; None
        if it has none that day."""
        self.checked(day, self.days)
        if day not in self._planned:
            return None
        with self._working:
            if day not in self._done:
                self.on(day)
            if day not in self._done:
                # Its state on that day was taken over, or given, rather
                # than worked out here: work the day out again, the same.
                self._next_day(day - 1, self.on(day - 1))
            return self._done[day]

    def lived_on(self, day: int) -> LivedT:
        """What the crop experienced on the run's day `day`, from 0 to its
        last."""
        self.checked(day, self.days - 1)
        with self._working:
            self._take_over(day + 1)
            if day >= len(self._lived):
                self._day(day, self.on(day))
            return self._lived[day]

    def seed(self, day: int, state: object, lived: Sequence[object]) -> None:
        """Take `state` as the crop on the run's `day`, and `lived` as what
        it experienced on each day before it, from a checkpoint of the same
        run (P09.5): later days carry on from them. Refused if it is not
        this crop's."""
        self.checked(day, self.days)
        if len(lived) != day:
            raise ValueError(f"a crop on day {day} has lived {day} days, not {len(lived)}")
        read = self.growth.read(state, lived)
        if read is None:
            raise ValueError(f"a crop of {self.growth.made_of} takes no others")
        own, days = read
        with self._working, self._keeping:
            if len(self._lived) < day:
                self._lived = days
            self._kept.setdefault(day, own)

    def carry_on_from(self, other: CropDays[StateT, LivedT], days: int) -> None:
        """Take over what `other` worked out of the run's first `days` days:
        what it experienced on them, and its states kept on those days and
        the next; and what it works out of them later, as this crop works
        its own days on. Only another crop of the same scenario, in a run
        whose air is the same through those days, and whose own crop
        actions are the same through the next, is the same crop."""
        with self._working:
            self._sources = [(source, through) for source, through in self._sources if source()]
            self._sources.append((weakref.ref(other), days))
            self._take_over(days)

    def _take_over(self, day: int) -> None:
        """Take over, from each crop carried on from, what it has worked out
        of the run's first `day` days, as far as the two are the same crop;
        while the other is living those very days, wait for it rather than
        live them beside it. Called with `_working` held."""
        for source, days in self._sources:
            other = source()
            if other is None:
                continue
            through = min(day, days)
            while True:
                # Only this request writes what this crop keeps: `_working` is
                # held. The two `_keeping` locks are never held together,
                # since two crops may carry on from each other.
                with other._kept_changed:
                    lived = other._lived[:through]
                    kept = [
                        (kept_day, state)
                        for kept_day, state in other._kept.items()
                        if kept_day <= through
                    ]
                    ahead = max(len(self._lived), len(lived))
                    waiting = other._working_through(ahead, through)
                    if waiting:
                        other._kept_changed.wait(LOOK_AGAIN_S)
                with self._keeping:
                    if len(self._lived) < len(lived):
                        self._lived = lived
                    for kept_day, state in kept:
                        if kept_day <= len(self._lived):
                            self._kept.setdefault(kept_day, state)
                    self._bounded(day)
                if not waiting:
                    break

    def _working_through(self, since: int, through: int) -> bool:
        """Whether a request is living this crop through a day past `since`
        and up to `through`, which a crop carrying on from this one would
        otherwise live itself. Called with `_keeping` held."""
        if self._stretch is None:
            return False
        start, end = self._stretch
        return start < through and since < min(end, through)

    def _day(self, day: int, state: StateT) -> LivedT:
        """What the crop, `state` on the run's day `day`, experienced on that
        day: kept, or worked out by its growth."""
        if day < len(self._lived):
            return self._lived[day]
        lived = self.growth.lived(day, state)
        with self._keeping:
            self._lived.append(lived)
        return lived

    def _keep(self, day: int, state: StateT) -> None:
        with self._keeping:
            self._kept[day] = state
            self._kept.move_to_end(day)
            self._bounded(day)

    def _bounded(self, day: int) -> None:
        """Drop the days kept longest ago beyond `KEPT_DAYS` and two: never
        the first, the latest or `day`. Called with `_keeping` held."""
        latest = max(self._kept)
        while len(self._kept) > KEPT_DAYS + 2:
            oldest = next(kept for kept in self._kept if kept not in (0, latest, day))
            del self._kept[oldest]
