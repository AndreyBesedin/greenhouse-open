"""The steps of a run's crop, however its model grows it (P14.8, decision
0062): what every crop of the run keeps and works out alike, whatever it
is made of, step by step at its model's step (P16.1, decision 0064).

A crop's growth (`Growth`) says what it is made of, its step, a whole
divisor of a day, and how it lives a step: its state at the run's start;
what it experienced on a step, worked out from the run's air and light; and
its state at the next step, once it has lived that one, after the next
step's crop work and its own crop actions. A crop grown plant by plant is
one, whose step is a day (`greenhouse_sim.core.crop.PlantGrowth`, decision
0024). `CropSteps` keeps the rest:

- **its steps in order:** the crop at step `s` has lived the run's first
  `s` steps, and what it experienced on each step is kept, so that its
  steps can be listed and its state at any step lived again from them,
  without the air or the light;
- **a few steps' states:** its first step's, the latest worked out's, and
  the few last asked for (`KEPT_STEPS`);
- **what its own crop actions did,** step by step (`StepWork`);
- **its steps taken over** from another crop of the same run, up to the
  first on which their air or their own crop actions differ
  (`carry_on_from`), and its state at a step given from a checkpoint
  (`seed`);
- **one request at a time** working it on, the others waiting for it and
  finding what it kept, and a crop carrying on from this one waiting for
  the steps a request is working through rather than living them beside it.

Since a step divides a day, the run's day `d` begins the crop's step
`d × steps_a_day`. Between two steps, the crop is as at the earlier
(`at`): its steps are worked out on their grid alone, however often, and
in whatever order, anyone asks for it (decision 0064).
"""

import threading
import weakref
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from greenhouse_sim.climate.run import LOOK_AGAIN_S
from greenhouse_sim.core.clock import DAY_S, steps_a_day, steps_ended
from greenhouse_sim.core.crop_actions import CropAction, CropEffect

# How many steps' states a crop keeps besides its first step's and its
# latest's: the last asked for.
KEPT_STEPS: Final = 2


@dataclass(frozen=True)
class CropDone:
    """What one of a run's own crop actions did, or why it was refused."""

    effect: CropEffect | None = None
    refusal: str | None = None


@dataclass(frozen=True)
class StepWork:
    """A step's own crop actions as the crop carried them out: what each
    did, in the order planned; and how long the history of each plant they
    act on was once that step's crop work was done, before them."""

    done: tuple[CropDone, ...]
    work_ends: Mapping[str, int]


class Growth[StateT, LivedT](Protocol):
    """How a run's crop is made and lives its steps: see the module. A
    growth keeps nothing of the steps it works out; `CropSteps` keeps
    them."""

    @property
    def step_s(self) -> float:
        """Its step, in seconds: a whole divisor of a day."""
        ...

    def first(self) -> StateT:
        """The crop at the run's start."""
        ...

    def lived(self, step: int, state: StateT) -> LivedT:
        """What the crop, `state` at the run's step `step`, experienced on
        that step."""
        ...

    def next_step(
        self, step: int, state: StateT, lived: LivedT, planned: Sequence[CropAction]
    ) -> tuple[StateT, StepWork | None]:
        """The crop at the run's step after `step`, `state` at it: once it
        has lived it as `lived`, after the next step's crop work and then
        the run's own crop actions `planned` for it, in their order; and
        what those did, if there were any."""
        ...

    @property
    def made_of(self) -> str:
        """What the crop is made of, as a refusal names it."""
        ...

    def read(self, state: object, lived: Sequence[object]) -> tuple[StateT, list[LivedT]] | None:
        """`state` as a state of this crop, and `lived` as what it
        experienced on each step before, as a checkpoint gives them back;
        None if they are not this crop's."""
        ...


class CropSteps[StateT, LivedT]:
    """A run's crop through its `steps`, made and lived as `growth` says,
    and worked as the run's own crop actions at each step ask (`planned`,
    by step): see the module. Refused if its growth's step does not divide
    a day."""

    def __init__(
        self,
        growth: Growth[StateT, LivedT],
        *,
        steps: int,
        planned: Mapping[int, tuple[CropAction, ...]],
    ) -> None:
        self.steps_a_day = steps_a_day(growth.step_s)
        self.steps = steps
        self.growth = growth
        self._planned = dict(planned)
        # What the planned crop actions of each step worked out did.
        self._done: dict[int, StepWork] = {}
        # What the crop experienced on each step worked out, from the first.
        self._lived: list[LivedT] = []
        # The crop at the steps kept: the first, the latest worked out, and
        # the last asked for.
        self._kept: OrderedDict[int, StateT] = OrderedDict({0: growth.first()})
        # One request at a time works a crop on; others wait for it, and
        # find what it kept.
        self._working = threading.RLock()
        # Held only to change what is kept, or to copy it: another crop
        # carrying on from this one copies it without waiting for a request
        # working this crop on.
        self._keeping = threading.Lock()
        # The steps a request is working the crop through, from the latest
        # kept before the one asked for to it, or None: a crop carrying on
        # from this one waits while they cover what it needs, rather than
        # live them beside this crop. Told under `_keeping`, and
        # `_kept_changed` is notified when they end.
        self._stretch: tuple[int, int] | None = None
        self._kept_changed = threading.Condition(self._keeping)
        # The crops this one carries on from (`carry_on_from`), each with the
        # steps through which it is the same crop: what they work out of
        # those steps is taken over again whenever this crop works a step
        # on, so that a request working one of them on is neither waited for
        # nor repeated. Held weakly: a crop the kept runs have forgotten is
        # not kept alive by those that carried on from it.
        self._sources: list[tuple[weakref.ref[CropSteps[StateT, LivedT]], int]] = []

    def checked(self, step: int, last: int) -> None:
        """Refused, naming its steps, if `step` is not from 0 to `last`."""
        if not 0 <= step <= last:
            raise ValueError(f"a run's crop has {self._named()[1]} 0 to {last}, not {step}")

    def _named(self) -> tuple[str, str]:
        """What a refusal calls one of its steps, and several: days, for a
        crop whose step is a day."""
        if self.growth.step_s == DAY_S:
            return "day", "days"
        return "step", f"steps of {self.growth.step_s:g} s"

    def on(self, step: int) -> StateT:
        """The crop at the run's step `step`, from 0 to its steps: once it
        has lived the steps before it, after that step's crop work."""
        self.checked(step, self.steps)
        with self._working:
            kept = self._kept.get(step)
            if kept is not None:
                with self._keeping:
                    self._kept.move_to_end(step)
                return kept
            self._take_over(step)
            start = max(kept_step for kept_step in self._kept if kept_step <= step)
            with self._keeping:
                self._stretch = (start, step)
            try:
                state = self._lived_through(start, step)
            finally:
                with self._kept_changed:
                    self._stretch = None
                    self._kept_changed.notify_all()
            self._keep(step, state)
            return state

    def at(self, time_s: float) -> StateT:
        """The crop `time_s` into the run, from its start to its end: once it
        has lived the steps ended by then, after the last one's crop work."""
        return self.on(steps_ended(time_s, self.growth.step_s))

    def _lived_through(self, start: int, step: int) -> StateT:
        state = self._kept[start]
        for lived in range(start, step):
            state = self._next_step(lived, state)
        return state

    def _next_step(self, lived: int, state: StateT) -> StateT:
        """The crop at the step after `lived`, `state` at it: once it has
        lived it, after the next step's crop work and its own crop
        actions."""
        state, work = self.growth.next_step(
            lived, state, self._step(lived, state), self._planned.get(lived + 1, ())
        )
        if work is not None:
            with self._keeping:
                self._done[lived + 1] = work
        return state

    def worked_on(self, step: int) -> StepWork | None:
        """What the run's own crop actions at its step `step` did, from 0 to
        its steps, the crop worked through that step if it has not been;
        None if it has none then."""
        self.checked(step, self.steps)
        if step not in self._planned:
            return None
        with self._working:
            if step not in self._done:
                self.on(step)
            if step not in self._done:
                # Its state at that step was taken over, or given, rather
                # than worked out here: work the step out again, the same.
                self._next_step(step - 1, self.on(step - 1))
            return self._done[step]

    def lived_on(self, step: int) -> LivedT:
        """What the crop experienced on the run's step `step`, from 0 to its
        last."""
        self.checked(step, self.steps - 1)
        with self._working:
            self._take_over(step + 1)
            if step >= len(self._lived):
                self._step(step, self.on(step))
            return self._lived[step]

    def seed(self, step: int, state: object, lived: Sequence[object]) -> None:
        """Take `state` as the crop at the run's `step`, and `lived` as what
        it experienced on each step before it, from a checkpoint of the same
        run (P09.5): later steps carry on from them. Refused if it is not
        this crop's."""
        self.checked(step, self.steps)
        if len(lived) != step:
            one, several = self._named()
            raise ValueError(f"a crop on {one} {step} has lived {step} {several}, not {len(lived)}")
        read = self.growth.read(state, lived)
        if read is None:
            raise ValueError(f"a crop of {self.growth.made_of} takes no others")
        own, steps = read
        with self._working, self._keeping:
            if len(self._lived) < step:
                self._lived = steps
            self._kept.setdefault(step, own)

    def carry_on_from(self, other: CropSteps[StateT, LivedT], steps: int) -> None:
        """Take over what `other` worked out of the run's first `steps`
        steps: what it experienced on them, and its states kept at those
        steps and the next; and what it works out of them later, as this
        crop works its own steps on. Only another crop of the same scenario,
        in a run whose air is the same through those steps, and whose own
        crop actions are the same through the next, is the same crop."""
        with self._working:
            self._sources = [(source, through) for source, through in self._sources if source()]
            self._sources.append((weakref.ref(other), steps))
            self._take_over(steps)

    def _take_over(self, step: int) -> None:
        """Take over, from each crop carried on from, what it has worked out
        of the run's first `step` steps, as far as the two are the same
        crop; while the other is living those very steps, wait for it rather
        than live them beside it. Called with `_working` held."""
        for source, steps in self._sources:
            other = source()
            if other is None:
                continue
            through = min(step, steps)
            while True:
                # Only this request writes what this crop keeps: `_working` is
                # held. The two `_keeping` locks are never held together,
                # since two crops may carry on from each other.
                with other._kept_changed:
                    lived = other._lived[:through]
                    kept = [
                        (kept_step, state)
                        for kept_step, state in other._kept.items()
                        if kept_step <= through
                    ]
                    ahead = max(len(self._lived), len(lived))
                    waiting = other._working_through(ahead, through)
                    if waiting:
                        other._kept_changed.wait(LOOK_AGAIN_S)
                with self._keeping:
                    if len(self._lived) < len(lived):
                        self._lived = lived
                    for kept_step, state in kept:
                        if kept_step <= len(self._lived):
                            self._kept.setdefault(kept_step, state)
                    self._bounded(step)
                if not waiting:
                    break

    def _working_through(self, since: int, through: int) -> bool:
        """Whether a request is living this crop through a step past `since`
        and up to `through`, which a crop carrying on from this one would
        otherwise live itself. Called with `_keeping` held."""
        if self._stretch is None:
            return False
        start, end = self._stretch
        return start < through and since < min(end, through)

    def _step(self, step: int, state: StateT) -> LivedT:
        """What the crop, `state` at the run's step `step`, experienced on
        that step: kept, or worked out by its growth."""
        if step < len(self._lived):
            return self._lived[step]
        lived = self.growth.lived(step, state)
        with self._keeping:
            self._lived.append(lived)
        return lived

    def _keep(self, step: int, state: StateT) -> None:
        with self._keeping:
            self._kept[step] = state
            self._kept.move_to_end(step)
            self._bounded(step)

    def _bounded(self, step: int) -> None:
        """Drop the steps kept longest ago beyond `KEPT_STEPS` and two: never
        the first, the latest or `step`. Called with `_keeping` held."""
        latest = max(self._kept)
        while len(self._kept) > KEPT_STEPS + 2:
            oldest = next(kept for kept in self._kept if kept not in (0, latest, step))
            del self._kept[oldest]
