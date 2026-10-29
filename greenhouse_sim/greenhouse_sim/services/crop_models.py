"""The crop's models as the services know them (P14.6, decision 0055).

Each model of the crop part is registered with all that tells it apart, so
that no service branches on its name. The registry
(`greenhouse_sim.scenarios.registry`) holds its name, version and
parameters; its registration here, under the same name (`CROP_MODELS`),
what the services ask of it:

- **its rung**, built from a scenario (`greenhouse_sim.biology.crop_contract.CropRung`);
- **its state in a checkpoint**: its plants and what each lived
  (`state`), and what no run of it reaches (`implausible`);
- **how its plants are drawn** (`drawn`);
- **how a walk measures a plant** (`measured`), and what a day's harvest
  round picked from one (`picked`);
- **what a replay reads beside a day's digest** (`probed`): the crop's
  organs and their plants' mean thermal time, none for a model without
  organs;
- **whether it takes the run's own crop actions** (`takes_crop_actions`),
  the harvests, lowerings and leaves removed a plan asks for (P13.5): the
  organ crop does, the simple crop does not.

A model may answer more than the crop part asks, as the organ crop answers
a plant's structure (`greenhouse_sim.services.crop.crop_plant`): that
answer stays its own route's.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.crop_contract import CropPlant, CropRung
from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.plant.organs import Fruit
from greenhouse_sim.biology.tomato.organ.development import daily_thermal_time
from greenhouse_sim.biology.tomato.organ.fruit import is_red
from greenhouse_sim.biology.tomato.organ.geometry import top_height_m
from greenhouse_sim.biology.tomato.organ.topology import HarvestFruit, Plant
from greenhouse_sim.biology.tomato.organ.transplants import DEVELOPMENT, TRANSPLANT_CD
from greenhouse_sim.core.crop import OrganRung
from greenhouse_sim.core.simple_crop import SimplePlant, SimpleRung
from greenhouse_sim.domain.crop import CropModel, FruitStatus
from greenhouse_sim.domain.organs import FruitStage
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scene.plants import crop_entities
from greenhouse_sim.scene.snapshot import SceneEntity, simple_plant_entities

CM_PER_M: Final = 100.0
# How far a plant's thermal time may be from the sum of the days it lived,
# relative to it: what adding them up in another order gives.
THERMAL_TIME_TOLERANCE: Final = 1e-9


class CropState(BaseModel):
    """The organ crop's state at a checkpoint's day: its plants, and what
    each experienced on each day before, by plant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plants: list[Plant] = []
    lived: list[dict[str, LocalEnvironment]] = []


class SimpleCropState(BaseModel):
    """The simple crop's state at a checkpoint's day: its plants, with the
    values the model keeps for each, and what each experienced on each day
    before, by plant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plants: list[SimplePlant] = []
    lived: list[dict[str, LocalEnvironment]] = []


# A crop model's state, as a checkpoint keeps it.
type CropModelState = CropState | SimpleCropState


@dataclass(frozen=True)
class Measured:
    """A plant as a walk would find it, without the walk's errors: how many
    fruits it bears, how many of them are ripe and their mass, and how high
    it stands, in cm."""

    plant_id: str
    fruits: int
    ripe: int
    ripe_mass_g: float
    height_cm: float


@dataclass(frozen=True)
class CropRegistration[PlantT: CropPlant]:
    """A crop model as the services know it, under its registry's name:
    see the module."""

    name: str
    rung: Callable[[ScenarioConfig], CropRung[PlantT]]
    state: type[CropModelState]
    # What no run of the model reaches in a checkpoint's state on its day,
    # which fits its run's shape, as reasons; none if it is plausible.
    implausible: Callable[[Any, int], list[str]]
    drawn: Callable[[Sequence[PlantT], ScenarioConfig], list[SceneEntity]]
    measured: Callable[[PlantT], Measured]
    # The fruits a plant's harvest round picked since `earlier`, and their
    # fresh mass, by the crop work alone, which ends where its history is
    # the given length, if it has one.
    picked: Callable[[PlantT, PlantT, int | None], tuple[int, float]]
    # The crop's organs, and its plants' mean thermal time, in °Cd.
    probed: Callable[[Sequence[PlantT]], tuple[int, float]]
    takes_crop_actions: bool


def _organ_implausible(state: CropState, day: int) -> list[str]:
    """A plant that breaks the structure's rules, or whose thermal time is
    not what the days it lived add up to."""
    problems: list[str] = []
    for plant in state.plants:
        problems += [f"{plant.plant_id}: {problem}" for problem in plant.problems()]
        added = TRANSPLANT_CD + sum(
            daily_thermal_time(lived[plant.plant_id].mean_temperature_c, DEVELOPMENT)
            for lived in state.lived
        )
        if not math.isclose(plant.thermal_time, added, rel_tol=THERMAL_TIME_TOLERANCE):
            problems.append(
                f"{plant.plant_id}'s thermal time is {plant.thermal_time:.6g} °Cd, and the "
                f"{day} days it lived add up to {added:.6g}"
            )
    return problems


def _organ_drawn(plants: Sequence[Plant], config: ScenarioConfig) -> list[SceneEntity]:
    return crop_entities(plants, config.layout.trainings(), config.envelope)


def _attached(plant: Plant) -> list[Fruit]:
    return [
        flower.fruit
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None and flower.fruit.stage == FruitStage.ATTACHED
    ]


def _organ_measured(plant: Plant) -> Measured:
    """The fruits attached, the red ones, and how high its top stands."""
    fruits = _attached(plant)
    red = [fruit for fruit in fruits if is_red(fruit.ripeness)]
    return Measured(
        plant_id=plant.plant_id,
        fruits=len(fruits),
        ripe=len(red),
        ripe_mass_g=sum(fruit.mass_g for fruit in red),
        height_cm=top_height_m(plant) * CM_PER_M,
    )


def _organ_picked(plant: Plant, earlier: Plant, until: int | None) -> tuple[int, float]:
    """The fruits its history picked since `earlier`, fruit by fruit."""
    picked = [
        event
        for event in plant.history[len(earlier.history) : until]
        if event.applied and isinstance(event.action, HarvestFruit)
    ]
    return len(picked), sum(event.harvested_g for event in picked)


def _organ_probed(plants: Sequence[Plant]) -> tuple[int, float]:
    organs = sum(1 for plant in plants for _ in plant.organs())
    thermal_cd = sum(plant.thermal_time for plant in plants) / len(plants) if plants else 0.0
    return organs, thermal_cd


def _simple_implausible(state: SimpleCropState, day: int) -> list[str]:
    """A plant not as many days old as the checkpoint's day."""
    return [
        f"{plant.plant_id} is {plant.plant.age_days} days old on day {day}"
        for plant in state.plants
        if plant.plant.age_days != day
    ]


def _simple_drawn(plants: Sequence[SimplePlant], config: ScenarioConfig) -> list[SceneEntity]:
    return simple_plant_entities([plant.plant for plant in plants], config.layout, config.envelope)


def _simple_measured(plant: SimplePlant) -> Measured:
    """The fruits not harvested, the ripe ones and their mass, and how tall
    its stem stands."""
    fruits = [
        fruit
        for truss in plant.plant.trusses
        for fruit in truss.fruits
        if fruit.status != FruitStatus.HARVESTED
    ]
    ripe = [fruit for fruit in fruits if fruit.status == FruitStatus.RIPE]
    return Measured(
        plant_id=plant.plant_id,
        fruits=len(fruits),
        ripe=len(ripe),
        ripe_mass_g=sum(fruit.mass_g for fruit in ripe),
        height_cm=plant.standing_cm(),
    )


def _harvested_fruits(plant: SimplePlant) -> int:
    return sum(
        fruit.status == FruitStatus.HARVESTED
        for truss in plant.plant.trusses
        for fruit in truss.fruits
    )


def _simple_picked(
    plant: SimplePlant, earlier: SimplePlant, _until: int | None
) -> tuple[int, float]:
    """Its fruits harvested since `earlier`, and the mass they added to its
    harvest: it keeps no history, and takes none of the run's own crop
    actions."""
    picked = _harvested_fruits(plant) - _harvested_fruits(earlier)
    return picked, plant.plant.cumulative_harvest_g - earlier.plant.cumulative_harvest_g


def _simple_probed(_plants: Sequence[SimplePlant]) -> tuple[int, float]:
    # It has no organs, nor thermal time.
    return 0, 0.0


ORGAN: Final = CropRegistration[Plant](
    name=CropModel.ORGAN.value,
    rung=lambda config: OrganRung(config.random_seed),
    state=CropState,
    implausible=_organ_implausible,
    drawn=_organ_drawn,
    measured=_organ_measured,
    picked=_organ_picked,
    probed=_organ_probed,
    takes_crop_actions=True,
)
SIMPLE: Final = CropRegistration[SimplePlant](
    name=CropModel.SIMPLE.value,
    rung=SimpleRung,
    state=SimpleCropState,
    implausible=_simple_implausible,
    drawn=_simple_drawn,
    measured=_simple_measured,
    picked=_simple_picked,
    probed=_simple_probed,
    takes_crop_actions=False,
)
# Each crop model's registration, by its registry's name.
CROP_MODELS: Final[dict[str, CropRegistration[Any]]] = {
    registration.name: registration for registration in (ORGAN, SIMPLE)
}


def registration(config: ScenarioConfig) -> CropRegistration[Any]:
    """The registration of the crop model a scenario's rows grow."""
    return CROP_MODELS[config.crop.kind]
