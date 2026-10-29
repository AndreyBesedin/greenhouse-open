"""A run's crop grown by area (P14.9, decision 0062): a model of the crop
grown per m² on each of its scopes, through the run's days.

- **Its instances** are its model on each of its scopes, a row of the crop
  rows each (`greenhouse_sim.world.scopes`), in the rows' order: each
  instance's state is the canopy per m² of the area its model declares
  (`AreaRung.basis`), every instance starting as its model plants it.
- **Each instance lives each day** in its day's course, which the run's
  driver profile gives it hour by hour (`greenhouse_sim.core.drivers`): the
  house's air and the light above its canopy.
- **No crop work and no crop actions:** a crop grown by area takes none of
  the run's crop actions, and a run of it is given none
  (`greenhouse_sim.services.crop_models.CropRegistration.crop_actions`);
  its harvest is its model's own rule.

Its days are kept as every run's crop keeps them
(`greenhouse_sim.core.crop_days.CropDays`): what is its own is how it grows
by area (`AreaGrowth`).
"""

from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.area_contract import AreaRung, DayCourse
from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.core.crop_days import CropDays, DayWork
from greenhouse_sim.world.scopes import CropScope

# Each scope's course on a day of the run, by its name.
type DayCourses = Callable[[int], dict[str, DayCourse]]


class AreaInstance[StateT: BaseModel](BaseModel):
    """An instance of a crop grown by area: its model on the scope
    `scope_id`, its canopy `state` per m² of its model's basis."""

    model_config = ConfigDict(frozen=True)

    scope_id: str
    state: StateT


class AreaGrowth[StateT: BaseModel]:
    """A crop grown by area (`greenhouse_sim.core.crop_days.Growth`): `rung`
    on each of `scopes`, each day in its course, as `courses` gives it."""

    def __init__(
        self, scopes: Sequence[CropScope], *, rung: AreaRung[StateT], courses: DayCourses
    ) -> None:
        self.rung = rung
        self.scopes = list(scopes)
        self._courses = courses

    def first(self) -> tuple[AreaInstance[StateT], ...]:
        planted = self.rung.planted()
        return tuple(AreaInstance(scope_id=scope.scope_id, state=planted) for scope in self.scopes)

    def lived(self, day: int, state: tuple[AreaInstance[StateT], ...]) -> dict[str, DayCourse]:
        """Each scope's course on the run's day `day`."""
        return self._courses(day)

    def next_day(
        self,
        day: int,
        state: tuple[AreaInstance[StateT], ...],
        lived: dict[str, DayCourse],
        planned: Sequence[CropAction],
    ) -> tuple[tuple[AreaInstance[StateT], ...], DayWork | None]:
        if planned:
            raise ValueError("a crop grown by area takes none of the run's crop actions")
        return tuple(
            AreaInstance(
                scope_id=instance.scope_id,
                state=self.rung.live_day(instance.state, lived[instance.scope_id]),
            )
            for instance in state
        ), None

    @property
    def made_of(self) -> str:
        return f"{self.rung.state_type.__name__} canopies"

    def read(
        self, state: object, lived: Sequence[object]
    ) -> tuple[tuple[AreaInstance[StateT], ...], list[dict[str, DayCourse]]] | None:
        """Its instances, as a sequence of each scope's, in their order, of
        its rung's states (`AreaRung.state_type`), and what each lived on
        each day, by scope."""
        if not isinstance(state, Sequence):
            return None
        days = [dict(day) for day in lived if isinstance(day, Mapping)]
        if len(days) != len(lived) or not all(
            isinstance(course, DayCourse) for day in days for course in day.values()
        ):
            return None
        instances = tuple(state)
        names = [scope.scope_id for scope in self.scopes]
        if [getattr(each, "scope_id", None) for each in instances] != names:
            return None
        if not all(
            isinstance(each, AreaInstance) and isinstance(each.state, self.rung.state_type)
            for each in instances
        ):
            return None
        own: tuple[AreaInstance[StateT], ...] = tuple(
            AreaInstance(scope_id=each.scope_id, state=each.state) for each in instances
        )
        return own, days


class AreaCrop[StateT: BaseModel](CropDays[tuple[AreaInstance[StateT], ...], dict[str, DayCourse]]):
    """A run's crop grown by `rung` on each of `scopes` through its `days`,
    each day in its course, as `courses` gives it: see the module."""

    growth: AreaGrowth[StateT]

    def __init__(
        self,
        scopes: Sequence[CropScope],
        *,
        rung: AreaRung[StateT],
        courses: DayCourses,
        days: int,
    ) -> None:
        self.rung = rung
        self.scopes = list(scopes)
        super().__init__(AreaGrowth(scopes, rung=rung, courses=courses), days=days, planned={})

    def instances_on(self, day: int) -> tuple[AreaInstance[StateT], ...]:
        """The crop on the run's day `day`, from 0 to its days: each scope's
        canopy once it has lived the days before it."""
        return self.on(day)

    def course(self, scope_id: str, day: int) -> DayCourse:
        """What a scope's canopy lived on the run's day `day`, from 0 to its
        last."""
        found = self.lived_on(day).get(scope_id)
        if found is None:
            raise LookupError(f"no scope {scope_id!r} in this crop")
        return found
