"""The plant lab: tomato plants from the organ-level model, to look at.

A client asks for a plant's structure, organ by organ, and for the scene a
viewer draws of the lab: its row of plants on a patch of ground, every organ
an entity that says which organ, and which plant, it is. The lab's plants are
transplants of one crop, each with traits drawn from the lab's seed, grown by
the development model day by day from day 0 to `LAST_DAY`, in one of the
lab's environments; with another beside it, every second plant lives in that
instead, so the two can be compared side by side. A run may also schedule
the protocol's crop actions, pruning, harvesting or lowering a plant at the
start of a day, which then shape that plant on every day after. The same seed
and schedule give the same row on every run; another seed, another row.
"""

from collections.abc import Iterator
from typing import Final

from greenhouse_protocol.actions import Inspect
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.plant.environment import Environment, LocalEnvironment
from greenhouse_sim.biology.tomato.organ.development import live_day
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.biology.tomato.organ.transplants import DEVELOPMENT, transplant
from greenhouse_sim.core.crop_actions import CropAction, carry_out
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
from greenhouse_sim.services.runs import CROP_SPELLINGS, crop_spelling, spelled_crop_action
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
# The lab's plants are transplants of one crop
# (`greenhouse_sim.biology.tomato.organ.transplants`), shown up to this day.
LAST_DAY: Final = 90
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


# The crop actions, as a request spells them (`runs.CROP_SPELLINGS`), that a
# run of the lab does not carry out on its plants (`crop_actions.carry_out`),
# and why not.
NOT_CARRIED_OUT: Final = {
    "lower_to": "its plants hang from no wire",
    "inspect": "an inspection changes no plant, and the lab keeps no outcomes",
}
# The crop actions it does carry out, as a request spells them.
LAB_KINDS: Final = tuple(kind for kind in CROP_SPELLINGS if kind not in NOT_CARRIED_OUT)


class LabStep(BaseModel):
    """A crop action of the protocol's that a run of the lab carries out on
    one of its plants at the start of a day (P13.9, decision 0046)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: int
    action: CropAction


class LabRun(BaseModel):
    """Which run of the lab: the day shown, the seed its row is drawn from,
    the environment its plants live in and, if `versus` names another, the
    environment every second plant lives in instead, beside the first; and
    the crop actions it carries out, in the order they are asked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: int = 0
    seed: int = LAB_SEED
    environment: str = REFERENCE
    versus: str | None = None
    actions: tuple[LabStep, ...] = ()


def lab_step(day: int, plant_id: str, kind: str, target: str) -> LabStep:
    """A crop action of a lab's run as a request spells it: on that day, of
    `kind` (`LAB_KINDS`) on the plant, acting on `target`, read as a run
    reads one (`runs.spelled_crop_action`). Refused (`InvalidRequest`) if it
    is none, saying what it wants, or by name if it is an inspection; the
    run it is given to is checked for the rest, its plant, its day and a
    lowering to a head room, when it is shown."""
    if kind not in CROP_SPELLINGS:
        known = ", ".join(LAB_KINDS)
        raise InvalidRequest(f"the plant lab has no action {kind!r}, only {known}")
    match spelled_crop_action(plant_id, kind, target):
        case Inspect():
            raise InvalidRequest(_not_carried_out(kind))
        case action:
            return LabStep(day=day, action=action)


def _not_carried_out(kind: str) -> str:
    return f"the plant lab does not carry out {kind}: {NOT_CARRIED_OUT[kind]}"


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


def _checked_run(run: LabRun) -> None:
    if not 0 <= run.day <= LAST_DAY:
        raise InvalidRequest(f"the plant lab runs from day 0 to day {LAST_DAY}, not day {run.day}")
    if run.seed < 0:
        raise InvalidRequest(f"a seed is a whole number from 0, not {run.seed}")
    for name in (run.environment, run.versus):
        if name is not None and name not in ENVIRONMENTS:
            known = ", ".join(ENVIRONMENTS)
            raise InvalidRequest(f"the plant lab has no environment {name!r}, only {known}")
    for step in run.actions:
        if step.action.plant_id not in plant_ids():
            raise InvalidRequest(f"the plant lab has no plant {step.action.plant_id!r} to act on")
        kind, _ = crop_spelling(step.action)
        if kind in NOT_CARRIED_OUT:
            raise InvalidRequest(_not_carried_out(kind))
        if not 0 <= step.day <= LAST_DAY:
            raise InvalidRequest(
                f"the plant lab runs from day 0 to day {LAST_DAY}, not day {step.day}"
            )


def _days(plant_id: str, run: LabRun, environment: Environment) -> Iterator[Plant]:
    """The plant on each day of the run up to its day, as it is shown: after
    that day's actions, each carried out as a run carries it out."""
    plant = transplant(plant_id, run.seed)
    for day in range(run.day + 1):
        for step in run.actions:
            if step.day == day and step.action.plant_id == plant_id:
                plant = carry_out(plant, step.action).plant
        yield plant
        if day < run.day:
            plant = live_day(plant, environment.local(plant_id, day), DEVELOPMENT)


def _lab_plant(plant_id: str, run: LabRun, environment: Environment) -> Plant:
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
    _checked_run(run)
    environment = LabEnvironment(run)
    found = {}
    for plant_id in plant_ids():
        *earlier, plant = _days(plant_id, run, environment)
        problems = plant.problems()
        if earlier:
            problems += plant.problems_since(earlier[-1])
        found[plant_id] = problems
    return LabChecks(day=run.day, problems=found)


def structure(run: LabRun | None = None, plant_id: str = LAB_PLANT_ID) -> Plant:
    """One of the lab's plants on its run's day, organ by organ."""
    run = LabRun() if run is None else run
    _checked_run(run)
    if plant_id not in plant_ids():
        raise NotFound(f"the plant lab has no plant {plant_id!r}")
    return _lab_plant(plant_id, run, LabEnvironment(run))


def scene(run: LabRun | None = None) -> SceneSnapshot:
    """The lab's row on its run's day, on its ground, as a viewer draws it,
    each plant's entities naming the environment it lives in."""
    run = LabRun() if run is None else run
    _checked_run(run)
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
            _lab_plant(plant_id, run, environment),
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
