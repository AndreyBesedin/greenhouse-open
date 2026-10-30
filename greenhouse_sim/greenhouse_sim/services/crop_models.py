"""The crop's models as the services know them (P14.6, decisions 0055 and
0062).

Each model of the crop part is registered with all that tells it apart, so
that no service branches on its name, nor asks which model it holds: it
asks what the model declares. The registry
(`greenhouse_sim.scenarios.registry`) holds its name, version and
parameters; its registration here, under the same name (`CROP_MODELS`),
its declarations:

- **its state in a checkpoint**: its plants and what each lived
  (`state`), and what no run of it reaches (`implausible`);
- **how it grows single plants** (`plants`, a `PlantAdapter`), if it does: its rung,
  built from a scenario (`greenhouse_sim.biology.crop_contract.CropRung`);
  how its plants are drawn (`drawn`); how a walk measures a plant
  (`measured`), and what a day's harvest round picked from one (`picked`);
  and what a replay reads beside a day's digest (`probed`): the crop's
  organs and their plants' mean thermal time, none for a model without
  organs;
- **how it grows by area** (`area`, an `AreaAdapter`), if it does: its
  rung, its driver profile, and how its instances are drawn (decision
  0062);
- **the run's own crop actions it takes** (`crop_actions`), by kind: the
  harvests, lowerings, leaves removed and inspections a plan asks for
  (P13.5), which the run routes to it; none for a model that takes none,
  whose run refuses them, saying why. The organ crop takes them, the
  simple crop none.

A declaration a model may lack is optional, so that the type checker makes
every service handle a model without it, rather than a flag or a name it
might forget to ask. A model may answer more than the crop part asks, as
the organ crop answers a plant's structure
(`greenhouse_sim.services.crop.crop_plant`): that answer stays its own
route's, which asks what its plants are (`CropRung.plant_type`).
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from greenhouse_protocol.actions import ActionKind
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.area_contract import AreaRung, StepCourse
from greenhouse_sim.biology.crop_contract import CropPlant, CropRung
from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.plant.organs import Fruit
from greenhouse_sim.biology.tomato.organ.development import daily_thermal_time
from greenhouse_sim.biology.tomato.organ.fruit import is_red
from greenhouse_sim.biology.tomato.organ.geometry import top_height_m
from greenhouse_sim.biology.tomato.organ.topology import HarvestFruit, Plant
from greenhouse_sim.biology.tomato.organ.transplants import DEVELOPMENT, TRANSPLANT_CD
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters, TomgroState
from greenhouse_sim.core.area_crop import AreaInstance
from greenhouse_sim.core.crop import OrganRung
from greenhouse_sim.core.drivers import DriverProfile, driver_profile
from greenhouse_sim.core.simple_crop import SimplePlant, SimpleRung
from greenhouse_sim.core.tomgro_crop import TomgroRung
from greenhouse_sim.domain.crop import CropModel, FruitStatus
from greenhouse_sim.domain.organs import FruitStage
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import ReducedTomgroCrop
from greenhouse_sim.scene.plants import crop_entities
from greenhouse_sim.scene.snapshot import SceneEntity, canopy_entity, simple_plant_entities
from greenhouse_sim.world.scopes import row_scopes

CM_PER_M: Final = 100.0
# How far a plant's thermal time may be from the sum of the days it lived,
# relative to it: what adding them up in another order gives.
THERMAL_TIME_TOLERANCE: Final = 1e-9


class _GrownByPlant(BaseModel):
    """What a crop grown plant by plant keeps at a checkpoint's day, as a
    run's crop takes it back: its plants, by name."""

    plants: list[Any]

    @property
    def kept(self) -> tuple[object, ...]:
        """What a run's crop takes back: its plants."""
        return tuple(self.plants)

    @property
    def named(self) -> list[str]:
        """What it is made of, by name: its plants."""
        return [plant.plant_id for plant in self.plants]


class CropState(_GrownByPlant):
    """The organ crop's state at a checkpoint's day: its plants, and what
    each experienced on each day before, by plant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plants: list[Plant] = []
    lived: list[dict[str, LocalEnvironment]] = []


class SimpleCropState(_GrownByPlant):
    """The simple crop's state at a checkpoint's day: its plants, with the
    values the model keeps for each, and what each experienced on each day
    before, by plant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plants: list[SimplePlant] = []
    lived: list[dict[str, LocalEnvironment]] = []


class AreaCropState[StateT: BaseModel](BaseModel):
    """A crop grown by area's state at a checkpoint's day: each scope's
    instance, its canopy per m² of its model's basis, and what each lived on
    each of its model's steps before, by scope (decision 0062). It has no
    plants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    instances: list[AreaInstance[StateT]] = []
    lived: list[dict[str, StepCourse]] = []

    @property
    def plants(self) -> list[CropPlant]:
        """None: a crop grown by area has no plants."""
        return []

    @property
    def kept(self) -> tuple[object, ...]:
        """What a run's crop takes back: its instances."""
        return tuple(self.instances)

    @property
    def named(self) -> list[str]:
        """What it is made of, by name: its scopes."""
        return [instance.scope_id for instance in self.instances]


# Reduced-State TOMGRO's state in a checkpoint.
TomgroCropState = AreaCropState[TomgroState]

# A crop model's state, as a checkpoint keeps it: a member for each model.
type CropModelState = CropState | SimpleCropState | TomgroCropState


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
class PlantAdapter[PlantT: CropPlant]:
    """What the services ask of a crop model that grows single plants
    (decision 0062): see the module."""

    rung: Callable[[ScenarioConfig], CropRung[PlantT]]
    drawn: Callable[[Sequence[PlantT], ScenarioConfig], list[SceneEntity]]
    measured: Callable[[PlantT], Measured]
    # The fruits a plant's harvest round picked since `earlier`, and their
    # fresh mass, by the crop work alone, which ends where its history is
    # the given length, if it has one.
    picked: Callable[[PlantT, PlantT, int | None], tuple[int, float]]
    # The crop's organs, and its plants' mean thermal time, in °Cd.
    probed: Callable[[Sequence[PlantT]], tuple[int, float]]


@dataclass(frozen=True)
class AreaAdapter[StateT: BaseModel]:
    """What the services ask of a crop model grown by area (decision 0062):
    its rung, built from a scenario; the driver profile through which the
    run gives it its drivers, as its parameters name it; and how its
    instances are drawn, none of them as plants."""

    rung: Callable[[ScenarioConfig], AreaRung[StateT]]
    profile: Callable[[ScenarioConfig], DriverProfile]
    drawn: Callable[[Sequence[AreaInstance[StateT]], ScenarioConfig], list[SceneEntity]]


@dataclass(frozen=True)
class CropActions:
    """The run's own crop actions a crop model takes (P13.5), by kind,
    carried out on its plants by its rung (`CropRung.carry_out`)."""

    kinds: frozenset[ActionKind]


@dataclass(frozen=True)
class CropRegistration[PlantT: CropPlant]:
    """A crop model as the services know it, under its registry's name:
    see the module."""

    name: str
    state: type[CropModelState]
    # What no run of the model reaches in a checkpoint's state on its day,
    # which fits its run's shape, as reasons; none if it is plausible.
    implausible: Callable[[Any, int], list[str]]
    # How it grows single plants, or by area: one of the two.
    plants: PlantAdapter[PlantT] | None
    area: AreaAdapter[Any] | None
    # None for a model that takes none of the run's own crop actions.
    crop_actions: CropActions | None


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


def _tomgro_crop(config: ScenarioConfig) -> ReducedTomgroCrop:
    """A scenario's Reduced-State TOMGRO section, which its rows grow."""
    crop = config.crop
    if not isinstance(crop, ReducedTomgroCrop):
        raise ValueError(f"{config.greenhouse_id}'s rows grow {crop.kind}, not reduced_tomgro")
    return crop


def _tomgro_rung(config: ScenarioConfig) -> TomgroRung:
    """The model with its parameter set, its light read at its section's
    canopy height."""
    return TomgroRung(TomgroParameters(), _tomgro_crop(config).canopy_height_m)


def _tomgro_implausible(state: TomgroCropState, _day: int) -> list[str]:
    """A canopy that is not finite, or whose leaf area index is past the
    most the model grows."""
    most = TomgroParameters().lai_max
    problems = []
    for instance in state.instances:
        canopy = instance.state
        if not all(map(math.isfinite, canopy.model_dump().values())):
            problems.append(f"{instance.scope_id}'s canopy is not finite")
        elif canopy.lai > most:
            problems.append(
                f"{instance.scope_id}'s leaf area index is {canopy.lai:.6g}, past {most:.6g}"
            )
    return problems


def _tomgro_drawn(
    instances: Sequence[AreaInstance[TomgroState]], config: ScenarioConfig
) -> list[SceneEntity]:
    """Each row's canopy, drawn as a proxy (decision 0062): as tall as its
    section's canopy height, as dense as the light its leaf area index
    takes, `1 - exp(-K · LAI)`, with the model's five states, per m² of
    floor."""
    rung = _tomgro_rung(config)
    scopes = {scope.scope_id: scope for scope in row_scopes(config.layout, config.envelope)}
    return [
        canopy_entity(
            scopes[instance.scope_id],
            config.envelope,
            entity_id=f"{config.greenhouse_id}_{instance.scope_id}_canopy",
            height_m=rung.canopy_height_m,
            density=1 - math.exp(-rung.parameters.k * instance.state.lai),
            properties={
                "model": CropModel.REDUCED_TOMGRO.value,
                "basis": rung.basis.value,
                "nodes": instance.state.n,
                "lai": instance.state.lai,
                "dry_weight_g_m2": instance.state.w,
                "fruit_g_m2": instance.state.wf,
                "mature_fruit_g_m2": instance.state.wm,
            },
        )
        for instance in instances
    ]


# The run's own crop actions the organ crop takes: every kind a plan may
# ask of a plant (`greenhouse_sim.services.runs.CROP_KINDS`).
ORGAN_CROP_ACTIONS: Final = CropActions(
    frozenset({ActionKind.HARVEST, ActionKind.LOWER, ActionKind.REMOVE_LEAF, ActionKind.INSPECT})
)

ORGAN: Final = CropRegistration[Plant](
    name=CropModel.ORGAN.value,
    state=CropState,
    implausible=_organ_implausible,
    plants=PlantAdapter(
        rung=lambda config: OrganRung(config.random_seed),
        drawn=_organ_drawn,
        measured=_organ_measured,
        picked=_organ_picked,
        probed=_organ_probed,
    ),
    area=None,
    crop_actions=ORGAN_CROP_ACTIONS,
)
SIMPLE: Final = CropRegistration[SimplePlant](
    name=CropModel.SIMPLE.value,
    state=SimpleCropState,
    implausible=_simple_implausible,
    plants=PlantAdapter(
        rung=SimpleRung,
        drawn=_simple_drawn,
        measured=_simple_measured,
        picked=_simple_picked,
        probed=_simple_probed,
    ),
    area=None,
    # Its crop work's harvests and lowerings are its rung's; it takes none
    # of a plan's (P14.3).
    crop_actions=None,
)
REDUCED_TOMGRO: Final = CropRegistration[Any](
    name=CropModel.REDUCED_TOMGRO.value,
    state=TomgroCropState,
    implausible=_tomgro_implausible,
    plants=None,
    area=AreaAdapter(
        rung=_tomgro_rung,
        profile=lambda config: driver_profile(
            _tomgro_crop(config).driver_profile, _tomgro_crop(config).driver_profile_version
        ),
        drawn=_tomgro_drawn,
    ),
    # Its harvest is the model's own rule; it takes none of a plan's.
    crop_actions=None,
)
# Each crop model's registration, by its registry's name.
CROP_MODELS: Final[dict[str, CropRegistration[Any]]] = {
    registration.name: registration for registration in (ORGAN, SIMPLE, REDUCED_TOMGRO)
}


def registration(config: ScenarioConfig) -> CropRegistration[Any]:
    """The registration of the crop model a scenario's rows grow."""
    return CROP_MODELS[config.crop.kind]
