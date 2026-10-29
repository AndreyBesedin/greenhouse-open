"""A run's crop through the run's days (P09.3), grown by one of the crop
part's models, a rung of its ladder (decision 0035): organ by organ
(`OrganRung`), or by the simple daily model (`greenhouse_sim.core.simple_crop`,
P14.3). What a model must do is its contract, `CropRung`
(`greenhouse_sim.biology.crop_contract`).

- **Its plants** are transplants of one crop, each at its planting
  position, trained as its layout trains it, its traits drawn from the
  scenario's seed.
- **Each plant lives each day** in what the run makes of it, through the
  plant model's `Environment` contract (decision 0024): the house's mean air
  temperature and CO₂ through the day, the same for every plant
  (`greenhouse_sim.climate.house`); its own daily light integral, read at
  its crown's top with every crown as tall as its plant stands that day,
  where its stem rises (`greenhouse_sim.solar.plants`), so that a taller row shades its
  neighbours more as the season goes on; and a water status of 1, since
  nothing models the irrigation yet. Each model takes from it what it
  reads.
- **The crop work** is the run's (`CropWork`): a harvest round at the start
  of every `harvest_every_days`th day picks every red fruit; then a
  lowering round, every `lower_every_days`, lowers each plant that hangs
  from a wire to keep its top under it, the organ crop laying its bare
  lower stem down along the lane its training gives it
  (`greenhouse_sim.world.training`).
- **A run's own crop actions** (`planned`), the harvests, lowerings and
  leaves removed its plan asks for at the start of a day, are carried out
  after that day's crop work, in the plan's order
  (`greenhouse_sim.core.crop_actions`), and what each did, or why it was
  refused, is kept (`worked_on`).
- **At a midnight** the plants live the day that ends, then the day that
  starts begins with its crop work, as the run's timeline lists them
  (`greenhouse_sim.core.timeline`). The crop on day `d` has lived the run's
  first `d` days.

Its days are kept as every run's crop keeps them, whatever its model
(`greenhouse_sim.core.crop_days.CropDays`, P14.8): worked out in order, what
each plant experienced on each kept, so that its days can be listed and its
plants on any day lived again from them, without the air or the light; its
plants kept on its first day, on the latest worked out, and on the few last
asked for; and its days taken over from another's, up to the first on which
their runs' air, or their own crop actions, differ (`carry_on_from`). What
is its own is how it grows plant by plant (`PlantGrowth`).
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Final, Protocol, TypeIs

from greenhouse_protocol.actions import Harvest, HarvestScope, Lower
from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveInt

from greenhouse_sim.biology.crop_contract import CropPlant, CropRung
from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.development import live_day
from greenhouse_sim.biology.tomato.organ.geometry import rising_point, stem_height_m
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.biology.tomato.organ.transplants import DEVELOPMENT, transplant
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.crop_actions import CarriedOut, CropAction, carry_out
from greenhouse_sim.core.crop_days import CropDays, CropDone, DayWork
from greenhouse_sim.core.stopwatch import Stopwatch, timed
from greenhouse_sim.solar.plants import Crown
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.training import Training

# The parts of a day a benchmark times (P09.8): the house's air through it,
# the plants' light, and the plants living it, with their crop work.
HOUSE_AIR: Final = "house_air"
PLANTS_LIGHT: Final = "plants_light"
PLANTS_DAYS: Final = "plants_days"


class CropLight(Protocol):
    """The light on a crop's crowns (`greenhouse_sim.solar.plants.PlantLight`):
    each plant's PAR at a moment, and its daily light integral on a day."""

    def par_at(self, time_s: float) -> dict[str, float]:
        """Each plant's PAR `time_s` into the run, in µmol/m²/s."""
        ...

    def daily_light_integral(self, day: int = 0) -> dict[str, float]:
        """Each plant's daily light integral on the run's `day`th day, in
        mol/m²/d."""
        ...


class OrganRung:
    """The organ crop as a rung of the run's crop: the scenario's transplants
    (`greenhouse_sim.biology.tomato.organ.transplants`), drawn from its
    `seed`, each living its days by the organ model's development, and the
    crop work its operations (`greenhouse_sim.core.crop_actions`); its
    crown rises where its stem does, as tall as its standing stem."""

    def __init__(self, seed: int) -> None:
        self._seed = seed

    @property
    def plant_type(self) -> type[Plant]:
        return Plant

    def transplant(self, plant_id: str) -> Plant:
        return transplant(plant_id, self._seed)

    def live_day(self, plant: Plant, environment: LocalEnvironment) -> Plant:
        return live_day(plant, environment, DEVELOPMENT)

    def carry_out(
        self, plant: Plant, action: CropAction, training: Training | None
    ) -> CarriedOut[Plant]:
        return carry_out(plant, action, training)

    def crown(self, plant: Plant, training: Training) -> tuple[Vector3, float]:
        return rising_point(plant, training.path), stem_height_m(plant)

    def recorded(self, plant: Plant) -> int:
        return len(plant.history)


def crowns[PlantT: CropPlant](
    rung: CropRung[PlantT],
    plants: Sequence[PlantT],
    trainings: Sequence[Training],
    envelope: Envelope,
) -> list[Crown]:
    """Each plant's crown, the first trained as the first of `trainings`
    says in `envelope`, and so on: standing where its model says it rises,
    as tall as it says it stands; none for a plant with no stem showing."""
    placed = []
    for plant, training in zip(plants, trainings, strict=False):
        foot = training.position.point
        rises, height = rung.crown(plant, training)
        if height > 0:
            base = Vector3(x=foot.x + rises.x, y=foot.y + rises.y, z=foot.z + rises.z)
            placed.append(
                Crown(plant_id=plant.plant_id, base=envelope.to_world(base), height_m=height)
            )
    return placed


# The house's mean air through a day of the run, from 0.
type DayAir = Callable[[int], HouseAir]
# The light on the crop on a day of the run, its crowns as given.
type CrownLight = Callable[[int, Sequence[Crown]], CropLight]


class CropWork(BaseModel):
    """What a run does to its crop, at the start of its days: a harvest round
    every `harvest_every_days` days from its start, picking every red fruit;
    and then a lowering round every `lower_every_days`, which leaves each
    plant hanging from a wire with its top `head_room_m` or more under it;
    neither if unset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    harvest_every_days: PositiveInt | None = None
    lower_every_days: PositiveInt | None = None
    head_room_m: NonNegativeFloat = 0.3

    def harvests_on(self, day: int) -> bool:
        """Whether a harvest round starts the run's day `day`."""
        return _due(self.harvest_every_days, day)

    def lowers_on(self, day: int) -> bool:
        """Whether a lowering round starts the run's day `day`."""
        return _due(self.lower_every_days, day)

    def actions_on(self, day: int, plant_id: str) -> list[CropAction]:
        """The crop actions that start the run's day `day` on a plant, in
        order: a harvest of every ripe fruit, then a lowering to the head
        room under its wire, each if it is due."""
        actions: list[CropAction] = []
        if self.harvests_on(day):
            actions.append(Harvest(plant_id=plant_id, scope=HarvestScope.RIPE))
        if self.lowers_on(day):
            actions.append(Lower(plant_id=plant_id, to_head_room_m=self.head_room_m))
        return actions


def _due(days: int | None, day: int) -> bool:
    """Whether a task done every `days` days, if at all, starts the run's
    day `day`: never its first."""
    return days is not None and day > 0 and day % days == 0


class PlantGrowth[PlantT: CropPlant]:
    """A crop grown plant by plant (`greenhouse_sim.core.crop_days.Growth`):
    `transplants` grown by `rung`, the first plant trained as the first of
    `trainings` says in `envelope`, and so on, each day in `air` and its own
    `light`, worked as `work` says, and then as the run's own crop actions
    on that day ask. A `watch` times the parts of each day it works out."""

    def __init__(
        self,
        transplants: Sequence[PlantT],
        trainings: Sequence[Training],
        envelope: Envelope,
        *,
        rung: CropRung[PlantT],
        air: DayAir,
        light: CrownLight,
        work: CropWork,
        watch: Stopwatch | None = None,
    ) -> None:
        self.rung = rung
        self.light = light
        self._transplants = tuple(transplants)
        self._trainings = list(trainings)
        self._envelope = envelope
        self._air = air
        self._work = work
        self._watch = watch

    def first(self) -> tuple[PlantT, ...]:
        return self._transplants

    def lived(self, day: int, state: tuple[PlantT, ...]) -> dict[str, LocalEnvironment]:
        """What each plant experienced on the run's day `day`: the house's
        air, and its own light."""
        with timed(self._watch, HOUSE_AIR):
            air = self._air(day)
        with timed(self._watch, PLANTS_LIGHT):
            light = self.light(day, self.crowns(state)).daily_light_integral(day)
        return {
            plant.plant_id: LocalEnvironment(
                mean_temperature_c=air.temperature_c,
                par_mol_m2_day=light.get(plant.plant_id, 0.0),
                co2_ppm=air.co2_ppm,
            )
            for plant in state
        }

    def next_day(
        self,
        day: int,
        state: tuple[PlantT, ...],
        lived: dict[str, LocalEnvironment],
        planned: Sequence[CropAction],
    ) -> tuple[tuple[PlantT, ...], DayWork | None]:
        with timed(self._watch, PLANTS_DAYS):
            plants = tuple(
                self._worked(day + 1, self.rung.live_day(plant, lived[plant.plant_id]), training)
                for plant, training in zip(state, self._trainings, strict=False)
            )
            if not planned:
                return plants, None
            return self._carried_out(plants, planned)

    @property
    def made_of(self) -> str:
        return f"{self.rung.plant_type.__name__} plants"

    def read(
        self, state: object, lived: Sequence[object]
    ) -> tuple[tuple[PlantT, ...], list[dict[str, LocalEnvironment]]] | None:
        """Its plants, as a sequence of its rung's (`CropRung.plant_type`),
        and what each experienced on each day, by plant."""
        if not isinstance(state, Sequence):
            return None
        plants = tuple(state)
        days = [dict(day) for day in lived if isinstance(day, Mapping)]
        if len(days) != len(lived) or not all(
            isinstance(environment, LocalEnvironment)
            for day in days
            for environment in day.values()
        ):
            return None
        return (plants, days) if _of_type(plants, self.rung.plant_type) else None

    def crowns(self, plants: Sequence[PlantT]) -> list[Crown]:
        """Its plants' crowns, `plants` on a day."""
        return crowns(self.rung, plants, self._trainings, self._envelope)

    def _worked(self, day: int, plant: PlantT, training: Training) -> PlantT:
        """The plant after the crop work that starts the run's day `day`, its
        crop actions carried out in order (`CropWork.actions_on`); a plant
        that hangs from no wire is not lowered."""
        for action in self._work.actions_on(day, plant.plant_id):
            plant = self.rung.carry_out(plant, action, training).plant
        return plant

    def _carried_out(
        self, plants: tuple[PlantT, ...], planned: Sequence[CropAction]
    ) -> tuple[tuple[PlantT, ...], DayWork]:
        """The crop after the run's own crop actions `planned` on a day, in
        their order, `plants` once its crop work was done; and what each
        did."""
        place = {plant.plant_id: index for index, plant in enumerate(plants)}
        worked = list(plants)
        work_ends = {
            action.plant_id: self.rung.recorded(worked[place[action.plant_id]])
            for action in planned
        }
        done = []
        for action in planned:
            index = place[action.plant_id]
            training = self._trainings[index] if index < len(self._trainings) else None
            carried = self.rung.carry_out(worked[index], action, training)
            worked[index] = carried.plant
            done.append(CropDone(carried.effect, carried.refusal))
        return tuple(worked), DayWork(tuple(done), work_ends)


def _of_type[PlantT: CropPlant](
    plants: tuple[object, ...], plant_type: type[PlantT]
) -> TypeIs[tuple[PlantT, ...]]:
    return all(isinstance(plant, plant_type) for plant in plants)


class RunCrop[PlantT: CropPlant](CropDays[tuple[PlantT, ...], dict[str, LocalEnvironment]]):
    """A run's crop of `transplants` through its `days`, grown by `rung`,
    the first plant trained as the first of `trainings` says in `envelope`,
    and so on: each day in `air` and its own `light`, worked as `work` says,
    and then as the run's own crop actions on that day ask (`planned`, by
    day). Its days are kept as every run's crop keeps them (`CropDays`), its
    plants grown plant by plant (`PlantGrowth`). It is the plant model's
    environment for its plants (`local`). A `watch` times the parts of each
    day it works out, for a benchmark."""

    growth: PlantGrowth[PlantT]

    def __init__(
        self,
        transplants: Sequence[PlantT],
        trainings: Sequence[Training],
        envelope: Envelope,
        *,
        rung: CropRung[PlantT],
        air: DayAir,
        light: CrownLight,
        work: CropWork,
        days: int,
        planned: Mapping[int, Sequence[CropAction]] | None = None,
        watch: Stopwatch | None = None,
    ) -> None:
        self.work = work
        self.rung = rung
        self._plant_ids = [plant.plant_id for plant in transplants]
        kept = {day: tuple(acts) for day, acts in (planned or {}).items() if acts}
        for day, acts in kept.items():
            if not 0 < day <= days:
                raise ValueError(f"a run's crop is worked on days 1 to {days}, not {day}")
            for action in acts:
                if action.plant_id not in self._plant_ids:
                    raise ValueError(f"a run's crop has no plant {action.plant_id!r}")
        growth = PlantGrowth(
            transplants,
            trainings,
            envelope,
            rung=rung,
            air=air,
            light=light,
            work=work,
            watch=watch,
        )
        super().__init__(growth, days=days, planned=kept)

    def plants_on(self, day: int) -> tuple[PlantT, ...]:
        """The crop on the run's day `day`, from 0 to its days: its plants
        once they have lived the days before it, after that day's crop
        work."""
        return self.on(day)

    def local(self, plant_id: str, day: int) -> LocalEnvironment:
        """What a plant experienced on the run's day `day`, from 0 to its
        last."""
        found = self.lived_on(day).get(plant_id)
        if found is None:
            raise LookupError(f"no plant {plant_id!r} in this crop")
        return found

    def environments(self, plant_id: str, days: int) -> list[LocalEnvironment]:
        """What a plant experienced on each of the run's first `days` days."""
        return [self.local(plant_id, day) for day in range(days)]

    def lived_through(self, day: int) -> list[dict[str, LocalEnvironment]]:
        """What each plant experienced on each of the run's first `day` days,
        by plant: what a checkpoint keeps beside the plants on `day`."""
        return [
            {plant_id: self.local(plant_id, lived) for plant_id in self._plant_ids}
            for lived in range(day)
        ]

    def crowns_on(self, day: int) -> list[Crown]:
        """The plants' crowns on the run's day `day`, each as tall as its
        plant's stem stands."""
        return self.growth.crowns(self.plants_on(day))

    def light_on(self, day: int) -> CropLight:
        """The light on the crop on the run's day `day`, from 0 to its last,
        its crowns as tall as its plants stand that day."""
        self.checked(day, self.days - 1)
        return self.growth.light(day, self.crowns_on(day))
