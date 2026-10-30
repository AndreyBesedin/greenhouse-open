"""A run's crop grown by area (P14.9, decision 0062): a model of the crop
grown per m² on each of its scopes, through the run's days.

- **Its instances** are its model on each of its scopes, a row of the crop
  rows each (`greenhouse_sim.world.scopes`), in the rows' order: each
  instance's state is the canopy per m² of the area its model declares
  (`AreaRung.basis`), every instance starting as its model plants it.
- **Each instance lives each step** of its model (`AreaRung.step_s`,
  decision 0064) in its step's course, which the run's driver profile gives
  it hour by hour (`greenhouse_sim.core.drivers`): the house's air and the
  light above its canopy.
- **No crop work and no crop actions:** a crop grown by area takes none of
  the run's crop actions, and a run of it is given none
  (`greenhouse_sim.services.crop_models.CropRegistration.crop_actions`);
  its harvest is its model's own rule.

Its steps are kept as every run's crop keeps them
(`greenhouse_sim.core.crop_steps.CropSteps`), its days a view of them:
what is its own is how it grows by area (`AreaGrowth`).
"""

from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.area_contract import AreaRung, StepCourse
from greenhouse_sim.core.clock import steps_a_day
from greenhouse_sim.core.crop_actions import CropAction
from greenhouse_sim.core.crop_steps import CropSteps, StepWork
from greenhouse_sim.world.scopes import CropScope

# Each scope's course on a step of the run, by its name.
type StepCourses = Callable[[int], dict[str, StepCourse]]


class AreaInstance[StateT: BaseModel](BaseModel):
    """An instance of a crop grown by area: its model on the scope
    `scope_id`, its canopy `state` per m² of its model's basis."""

    model_config = ConfigDict(frozen=True)

    scope_id: str
    state: StateT


class AreaGrowth[StateT: BaseModel]:
    """A crop grown by area (`greenhouse_sim.core.crop_steps.Growth`): `rung`
    on each of `scopes`, each of its steps in its course, as `courses` gives
    it."""

    def __init__(
        self, scopes: Sequence[CropScope], *, rung: AreaRung[StateT], courses: StepCourses
    ) -> None:
        self.rung = rung
        self.scopes = list(scopes)
        self._courses = courses

    @property
    def step_s(self) -> float:
        return self.rung.step_s

    def first(self) -> tuple[AreaInstance[StateT], ...]:
        planted = self.rung.planted()
        return tuple(AreaInstance(scope_id=scope.scope_id, state=planted) for scope in self.scopes)

    def lived(self, step: int, state: tuple[AreaInstance[StateT], ...]) -> dict[str, StepCourse]:
        """Each scope's course on the run's step `step`."""
        return self._courses(step)

    def next_step(
        self,
        step: int,
        state: tuple[AreaInstance[StateT], ...],
        lived: dict[str, StepCourse],
        planned: Sequence[CropAction],
    ) -> tuple[tuple[AreaInstance[StateT], ...], StepWork | None]:
        if planned:
            raise ValueError("a crop grown by area takes none of the run's crop actions")
        return tuple(
            AreaInstance(
                scope_id=instance.scope_id,
                state=self.rung.live_step(instance.state, lived[instance.scope_id]),
            )
            for instance in state
        ), None

    @property
    def made_of(self) -> str:
        return f"{self.rung.state_type.__name__} canopies"

    def read(self, state: object) -> tuple[AreaInstance[StateT], ...] | None:
        """Its instances, as a sequence of each scope's, in their order, of
        its rung's states (`AreaRung.state_type`)."""
        if not isinstance(state, Sequence):
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
        return tuple(AreaInstance(scope_id=each.scope_id, state=each.state) for each in instances)


class AreaCrop[StateT: BaseModel](
    CropSteps[tuple[AreaInstance[StateT], ...], dict[str, StepCourse]]
):
    """A run's crop grown by `rung` on each of `scopes` through its `days`,
    each of its model's steps in its course, as `courses` gives it: see the
    module."""

    growth: AreaGrowth[StateT]

    def __init__(
        self,
        scopes: Sequence[CropScope],
        *,
        rung: AreaRung[StateT],
        courses: StepCourses,
        days: int,
    ) -> None:
        self.rung = rung
        self.scopes = list(scopes)
        growth = AreaGrowth(scopes, rung=rung, courses=courses)
        super().__init__(growth, steps=days * steps_a_day(growth.step_s), planned={})

    def instances_on(self, day: int) -> tuple[AreaInstance[StateT], ...]:
        """The crop on the run's day `day`, from 0 to its days: each scope's
        canopy once it has lived the days before it."""
        return self.on(day * self.steps_a_day)

    def course(self, scope_id: str, step: int) -> StepCourse:
        """What a scope's canopy lived on the run's step `step`, from 0 to
        its last."""
        found = self.lived_on(step).get(scope_id)
        if found is None:
            raise LookupError(f"no scope {scope_id!r} in this crop")
        return found
