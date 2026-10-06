"""The plant lab: tomato plants from the organ-level model, to look at.

A client asks for a plant's structure, organ by organ, and for the scene a
viewer draws of the lab: its row of plants on a patch of ground, every organ
an entity that says which organ, and which plant, it is. The lab's plants are
transplants of one crop, each with traits drawn from the lab's seed, grown by
the development model day by day from day 0 to `LAST_DAY`, in one of the
lab's environments; with another beside it, every second plant lives in that
instead, so the two can be compared side by side. A run may also schedule
actions, pruning, harvesting or lowering a plant at the start of a day, which
then shape that plant on every day after. The same seed and schedule give the
same row on every run; another seed, another row.
"""

from collections.abc import Iterator
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.tomato.organ.actions import act
from greenhouse_sim.biology.tomato.organ.development import (
    DevelopmentParams,
    develop,
    emerged,
    live_day,
)
from greenhouse_sim.biology.tomato.organ.environment import Environment, LocalEnvironment
from greenhouse_sim.biology.tomato.organ.topology import (
    HarvestFruit,
    HarvestTruss,
    LowerStem,
    Plant,
    PlantAction,
    RemoveLeaf,
    change_problems,
    topology_problems,
)
from greenhouse_sim.biology.tomato.organ.variation import VariationParams, draw_traits
from greenhouse_sim.scene.plants import plant_entities
from greenhouse_sim.scene.snapshot import (
    AXES_COLOR,
    AXES_LENGTH_M,
    Color,
    SceneEntity,
    SceneEntityKind,
    SceneSnapshot,
)
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.world.geometry import Axes, Plane, Transform, Vector3

LAB_ID: Final = "plant_lab"
# The lab's row: this many plants, this far apart along +y from the origin.
ROW_PLANTS: Final = 20
PLANT_SPACING_M: Final = 0.5
# The plant a client is shown first, at the row's start.
LAB_PLANT_ID: Final = "p01"
# The seed a client is shown first.
LAB_SEED: Final = 1
# The lab's ground reaches this far beyond its row on every side.
GROUND_MARGIN_M: Final = 1.5
GROUND_COLOR: Final = Color(r=0.45, g=0.36, b=0.27)
# The lab's plants are transplants this far into their development on day 0,
# shown up to this day.
TRANSPLANT_CD: Final = 230.0
LAST_DAY: Final = 90
# The crop: how its plants develop, their organs varying around each plant's
# sizes, and how its plants vary.
DEVELOPMENT: Final = DevelopmentParams(organ_size_cv=0.08)
VARIATION: Final = VariationParams()
# The environments the lab can keep its plants in, the same every day; the
# reference one is the conditions under which plants make all their
# potential growth.
REFERENCE: Final = "reference"
ENVIRONMENTS: Final = {
    REFERENCE: LocalEnvironment(mean_temperature_c=21.0, par_mol_m2_day=25.0, co2_ppm=800.0),
    "warm_bright": LocalEnvironment(mean_temperature_c=25.0, par_mol_m2_day=32.0, co2_ppm=1000.0),
    "cool_dim": LocalEnvironment(mean_temperature_c=17.0, par_mol_m2_day=8.0, co2_ppm=400.0),
    "dry": LocalEnvironment(
        mean_temperature_c=21.0, par_mol_m2_day=25.0, co2_ppm=800.0, water_status=0.5
    ),
}

_ORIGIN: Final = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))


# The actions a run can schedule, by name, with what each acts on.
ACTIONS: Final = {
    "remove_leaf": "a leaf",
    "harvest_fruit": "a fruit",
    "harvest_truss": "a truss",
    "lower_stem": "how many internodes",
}


class LabAction(BaseModel):
    """An action a run asks of one of its plants at the start of a day: its
    kind (`ACTIONS`) and the organ it acts on, or for lowering, by how many
    internodes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: int
    plant_id: str
    kind: str
    target: str


class LabRun(BaseModel):
    """Which run of the lab: the day shown, the seed its row is drawn from,
    the environment its plants live in and, if `versus` names another, the
    environment every second plant lives in instead, beside the first; and
    the actions it schedules, in the order they are asked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: int = 0
    seed: int = LAB_SEED
    environment: str = REFERENCE
    versus: str | None = None
    actions: tuple[LabAction, ...] = ()


def plant_ids() -> list[str]:
    """The row's plants, from its start."""
    return [f"p{place:02d}" for place in range(1, ROW_PLANTS + 1)]


def environments() -> dict[str, LocalEnvironment]:
    """The environments the lab can keep its plants in, by name."""
    return dict(ENVIRONMENTS)


class LabEnvironment:
    """The lab's plants' environment on a run: each plant in its run's
    environment, or every second one, from the row's second, in `versus`."""

    def __init__(self, run: LabRun) -> None:
        self._run = run

    def name(self, plant_id: str) -> str:
        """The name of the environment the plant lives in."""
        second = plant_ids().index(plant_id) % 2 == 1
        if second and self._run.versus is not None:
            return self._run.versus
        return self._run.environment

    def local(self, plant_id: str, day: int) -> LocalEnvironment:
        return ENVIRONMENTS[self.name(plant_id)]


def _checked(run: LabRun) -> None:
    if not 0 <= run.day <= LAST_DAY:
        raise InvalidRequest(f"the plant lab runs from day 0 to day {LAST_DAY}, not day {run.day}")
    if run.seed < 0:
        raise InvalidRequest(f"a seed is a whole number from 0, not {run.seed}")
    for name in (run.environment, run.versus):
        if name is not None and name not in ENVIRONMENTS:
            known = ", ".join(ENVIRONMENTS)
            raise InvalidRequest(f"the plant lab has no environment {name!r}, only {known}")
    for action in run.actions:
        _plant_action(action)
        if action.plant_id not in plant_ids():
            raise InvalidRequest(f"the plant lab has no plant {action.plant_id!r} to act on")
        if not 0 <= action.day <= LAST_DAY:
            raise InvalidRequest(
                f"the plant lab runs from day 0 to day {LAST_DAY}, not day {action.day}"
            )


def _plant_action(action: LabAction) -> PlantAction:
    """The plant action a scheduled one asks for."""
    match action.kind:
        case "remove_leaf":
            return RemoveLeaf(leaf_id=action.target)
        case "harvest_fruit":
            return HarvestFruit(fruit_id=action.target)
        case "harvest_truss":
            return HarvestTruss(truss_id=action.target)
        case "lower_stem":
            if not action.target.isdigit() or int(action.target) < 1:
                raise InvalidRequest(f"lower_stem wants how many internodes, not {action.target!r}")
            return LowerStem(internodes=int(action.target))
        case _:
            known = ", ".join(ACTIONS)
            raise InvalidRequest(f"the plant lab has no action {action.kind!r}, only {known}")


def _days(plant_id: str, run: LabRun, environment: Environment) -> Iterator[Plant]:
    """The plant on each day of the run up to its day, as it is shown: after
    that day's actions."""
    traits = draw_traits(run.seed, plant_id, VARIATION)
    plant = develop(emerged(plant_id, DEVELOPMENT, run.seed, traits), TRANSPLANT_CD, DEVELOPMENT)
    for day in range(run.day + 1):
        for action in run.actions:
            if action.day == day and action.plant_id == plant_id:
                plant = act(plant, _plant_action(action))
        yield plant
        if day < run.day:
            plant = live_day(plant, environment.local(plant_id, day), DEVELOPMENT)


def _grown(plant_id: str, run: LabRun, environment: Environment) -> Plant:
    *_, plant = _days(plant_id, run, environment)
    return plant


class LabChecks(BaseModel):
    """Whatever is wrong with each of the lab's plants on a run's day."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: int
    # By plant: the structure's rules it breaks, and anything it did since
    # the day before that a plant cannot. Empty when all is well.
    problems: dict[str, list[str]]


def checks(run: LabRun | None = None) -> LabChecks:
    """Each of the lab's plants on its run's day, held to the structure's
    rules, and to what a plant may do from one day to the next."""
    run = LabRun() if run is None else run
    _checked(run)
    environment = LabEnvironment(run)
    found = {}
    for plant_id in plant_ids():
        *earlier, plant = _days(plant_id, run, environment)
        problems = topology_problems(plant)
        if earlier:
            problems += change_problems(earlier[-1], plant)
        found[plant_id] = problems
    return LabChecks(day=run.day, problems=found)


def structure(run: LabRun | None = None, plant_id: str = LAB_PLANT_ID) -> Plant:
    """One of the lab's plants on its run's day, organ by organ."""
    run = LabRun() if run is None else run
    _checked(run)
    if plant_id not in plant_ids():
        raise NotFound(f"the plant lab has no plant {plant_id!r}")
    return _grown(plant_id, run, LabEnvironment(run))


def scene(run: LabRun | None = None) -> SceneSnapshot:
    """The lab's row on its run's day, on its ground, as a viewer draws it,
    each plant's entities naming the environment it lives in."""
    run = LabRun() if run is None else run
    _checked(run)
    environment = LabEnvironment(run)
    row_length = (ROW_PLANTS - 1) * PLANT_SPACING_M
    ground = SceneEntity(
        entity_id=f"{LAB_ID}_ground",
        kind=SceneEntityKind.GROUND,
        transform=Transform(position=Vector3(x=0.0, y=row_length / 2, z=0.0)),
        shape=Plane(size_x=2 * GROUND_MARGIN_M, size_y=row_length + 2 * GROUND_MARGIN_M),
        color=GROUND_COLOR,
        label="ground",
    )
    axes = SceneEntity(
        entity_id=f"{LAB_ID}_axes",
        kind=SceneEntityKind.AXES,
        transform=_ORIGIN,
        shape=Axes(length=AXES_LENGTH_M),
        color=AXES_COLOR,
        label="world axes",
    )
    plants = [
        entity
        for place, plant_id in enumerate(plant_ids())
        for entity in plant_entities(
            _grown(plant_id, run, environment),
            Transform(position=Vector3(x=0.0, y=place * PLANT_SPACING_M, z=0.0)),
            {"environment": environment.name(plant_id)},
        )
    ]
    return SceneSnapshot(
        greenhouse_id=LAB_ID, simulated_day=run.day, entities=[ground, *plants, axes]
    )


# The time lapse the screenshot tests draw: the lab's first plant, as the lab
# first shows it, at these ages, side by side along +x this far apart.
TIME_LAPSE_ID: Final = "plant_time_lapse"
TIME_LAPSE_DAYS: Final = (0, 30, 60, 90)
TIME_LAPSE_SPACING_M: Final = 1.0


def time_lapse() -> SceneSnapshot:
    """The lab's first plant on each of the time lapse's days, youngest
    first, standing side by side: each entity named for its day and saying
    which it is."""
    run = LabRun()
    width = (len(TIME_LAPSE_DAYS) - 1) * TIME_LAPSE_SPACING_M
    ground = SceneEntity(
        entity_id=f"{TIME_LAPSE_ID}_ground",
        kind=SceneEntityKind.GROUND,
        transform=Transform(position=Vector3(x=width / 2, y=0.0, z=0.0)),
        shape=Plane(size_x=width + 2 * GROUND_MARGIN_M, size_y=2 * GROUND_MARGIN_M),
        color=GROUND_COLOR,
        label="ground",
    )
    ages = [
        entity.model_copy(
            update={
                "entity_id": f"day{day:02d}_{entity.entity_id}",
                "properties": {**entity.properties, "day": day},
            }
        )
        for place, day in enumerate(TIME_LAPSE_DAYS)
        for entity in plant_entities(
            structure(run.model_copy(update={"day": day})),
            Transform(position=Vector3(x=place * TIME_LAPSE_SPACING_M, y=0.0, z=0.0)),
        )
    ]
    return SceneSnapshot(
        greenhouse_id=TIME_LAPSE_ID,
        simulated_day=TIME_LAPSE_DAYS[-1],
        entities=[ground, *ages],
    )
