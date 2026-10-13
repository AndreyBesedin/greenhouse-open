"""A run's crop, organ by organ, through the run's days (P09.3).

- **Its plants** are transplants of one crop
  (`greenhouse_sim.biology.tomato.organ.transplants`), each at its planting
  position, trained as its layout trains it, its traits drawn from the
  scenario's seed.
- **Each plant lives each day** in what the run makes of it, through the
  plant model's `Environment` contract (decision 0024): the house's mean air
  temperature and CO₂ through the day, the same for every plant
  (`greenhouse_sim.climate.house`); its own daily light integral, read at
  its crown's top with every crown as tall as its plant stands that day,
  where its stem rises (`greenhouse_sim.solar.plants`), so that a taller row shades its
  neighbours more as the season goes on; and a water status of 1, since
  nothing models the irrigation yet.
- **The crop work** is the run's (`CropWork`): a harvest round at the start
  of every `harvest_every_days`th day picks every red fruit, each a harvest
  in its plant's history; then a lowering round, every `lower_every_days`,
  lowers each plant that hangs from a wire to keep its top under it,
  laying its bare lower stem down along the lane its training gives it
  (`greenhouse_sim.world.training`).
- **At a midnight** the plants live the day that ends, then the day that
  starts begins with its crop work, as the run's timeline lists them
  (`greenhouse_sim.core.timeline`). The crop on day `d` has lived the run's
  first `d` days.

The crop's days are worked out in order, and what each plant experienced on
each is kept, so that its days can be listed and its plants on any day
lived again from them, without the air or the light. Its plants are kept on
its first day, on the latest worked out, and on the few last asked for. A
crop may take over another's days, up to the first on which their runs'
air differs (`carry_on_from`).
"""

import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveInt

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.actions import harvest_round, lowering_round
from greenhouse_sim.biology.tomato.organ.development import live_day
from greenhouse_sim.biology.tomato.organ.geometry import rising_point, stem_height_m
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.biology.tomato.organ.transplants import DEVELOPMENT
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.stopwatch import Stopwatch, timed
from greenhouse_sim.solar.plants import Crown
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.training import Training

# How many days' plants a crop keeps besides its first day's and its
# latest's: the last asked for.
KEPT_DAYS: Final = 2
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
        return _every(self.harvest_every_days, day)

    def lowers_on(self, day: int) -> bool:
        """Whether a lowering round starts the run's day `day`."""
        return _every(self.lower_every_days, day)


def _every(days: int | None, day: int) -> bool:
    return days is not None and day > 0 and day % days == 0


class RunCrop:
    """A run's crop of `transplants` through its `days`, the first plant
    trained as the first of `trainings` says in `envelope`, and so on: each
    day in `air` and its own `light`, and worked as `work` says. It is the
    plant model's environment for its plants (`local`). A `watch` times the
    parts of each day it works out, for a benchmark."""

    def __init__(
        self,
        transplants: Sequence[Plant],
        trainings: Sequence[Training],
        envelope: Envelope,
        *,
        air: DayAir,
        light: CrownLight,
        work: CropWork,
        days: int,
        watch: Stopwatch | None = None,
    ) -> None:
        self.days = days
        self.work = work
        self._watch = watch
        self._plant_ids = [plant.plant_id for plant in transplants]
        self._trainings = list(trainings)
        self._envelope = envelope
        self._air = air
        self._light = light
        # What each plant experienced on each day worked out, from the first.
        self._lived: list[dict[str, LocalEnvironment]] = []
        # The plants on the days kept: the first, the latest worked out, and
        # the last asked for.
        self._kept: OrderedDict[int, tuple[Plant, ...]] = OrderedDict({0: tuple(transplants)})
        # One request at a time works a crop on; others wait for it, and
        # find what it kept.
        self._working = threading.RLock()

    def _checked(self, day: int, last: int) -> None:
        if not 0 <= day <= last:
            raise ValueError(f"a run's crop has days 0 to {last}, not {day}")

    def plants_on(self, day: int) -> tuple[Plant, ...]:
        """The crop on the run's day `day`, from 0 to its days: its plants
        once they have lived the days before it, after that day's crop
        work."""
        self._checked(day, self.days)
        with self._working:
            kept = self._kept.get(day)
            if kept is not None:
                self._kept.move_to_end(day)
                return kept
            start = max(kept_day for kept_day in self._kept if kept_day <= day)
            plants = self._kept[start]
            for lived in range(start, day):
                environments = self._day(lived, plants)
                with timed(self._watch, PLANTS_DAYS):
                    plants = tuple(
                        self._worked(
                            lived + 1,
                            live_day(plant, environments[plant.plant_id], DEVELOPMENT),
                            training,
                        )
                        for plant, training in zip(plants, self._trainings, strict=False)
                    )
            self._keep(day, plants)
            return plants

    def local(self, plant_id: str, day: int) -> LocalEnvironment:
        """What a plant experienced on the run's day `day`, from 0 to its
        last."""
        self._checked(day, self.days - 1)
        with self._working:
            if day >= len(self._lived):
                self._day(day, self.plants_on(day))
            environments = self._lived[day]
        found = environments.get(plant_id)
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

    def seed(
        self,
        day: int,
        plants: Sequence[Plant],
        lived: Sequence[dict[str, LocalEnvironment]],
    ) -> None:
        """Take `plants` as the crop on the run's `day`, and `lived` as what
        they experienced on each day before it, from a checkpoint of the
        same run (P09.5): later days carry on from them."""
        self._checked(day, self.days)
        if len(lived) != day:
            raise ValueError(f"a crop on day {day} has lived {day} days, not {len(lived)}")
        with self._working:
            if len(self._lived) < day:
                self._lived = list(lived)
            self._kept.setdefault(day, tuple(plants))

    def crowns_on(self, day: int) -> list[Crown]:
        """The plants' crowns on the run's day `day`, each as tall as its
        plant's stem stands."""
        return self._crowns(self.plants_on(day))

    def light_on(self, day: int) -> CropLight:
        """The light on the crop on the run's day `day`, from 0 to its last,
        its crowns as tall as its plants stand that day."""
        self._checked(day, self.days - 1)
        return self._light(day, self.crowns_on(day))

    def carry_on_from(self, other: RunCrop, days: int) -> None:
        """Take over what `other` worked out of the run's first `days` days:
        what its plants experienced on them, and its plants kept on those
        days and the next. Only another crop of the same scenario, in a run
        whose air is the same through those days, is the same crop."""
        with self._working, other._working:
            if len(self._lived) < min(days, len(other._lived)):
                self._lived = other._lived[: min(days, len(other._lived))]
            for day, plants in other._kept.items():
                if day <= min(days, len(self._lived)):
                    self._kept.setdefault(day, plants)

    def _day(self, day: int, plants: tuple[Plant, ...]) -> dict[str, LocalEnvironment]:
        """What each of the crop's plants, `plants` on the run's day `day`,
        experienced on that day: kept, or worked out from the house's air
        and their light."""
        if day < len(self._lived):
            return self._lived[day]
        with timed(self._watch, HOUSE_AIR):
            air = self._air(day)
        with timed(self._watch, PLANTS_LIGHT):
            light = self._light(day, self._crowns(plants)).daily_light_integral(day)
        environments = {
            plant.plant_id: LocalEnvironment(
                mean_temperature_c=air.temperature_c,
                par_mol_m2_day=light.get(plant.plant_id, 0.0),
                co2_ppm=air.co2_ppm,
            )
            for plant in plants
        }
        self._lived.append(environments)
        return environments

    def _worked(self, day: int, plant: Plant, training: Training) -> Plant:
        """The plant after the crop work that starts the run's day `day`: a
        harvest round, then a lowering round, if either is due."""
        if self.work.harvests_on(day):
            plant = harvest_round(plant)
        if self.work.lowers_on(day) and training.wire_m is not None:
            plant = lowering_round(plant, training.wire_m - self.work.head_room_m, training.path)
        return plant

    def _crowns(self, plants: Sequence[Plant]) -> list[Crown]:
        """Each plant's crown, standing where its stem rises, as tall as
        its standing stem."""
        crowns = []
        for plant, training in zip(plants, self._trainings, strict=False):
            foot, rises = training.position.point, rising_point(plant, training.path)
            height = stem_height_m(plant)
            if height > 0:
                base = Vector3(x=foot.x + rises.x, y=foot.y + rises.y, z=foot.z + rises.z)
                crowns.append(
                    Crown(
                        plant_id=plant.plant_id,
                        base=self._envelope.to_world(base),
                        height_m=height,
                    )
                )
        return crowns

    def _keep(self, day: int, plants: tuple[Plant, ...]) -> None:
        self._kept[day] = plants
        self._kept.move_to_end(day)
        latest = max(self._kept)
        while len(self._kept) > KEPT_DAYS + 2:
            oldest = next(kept for kept in self._kept if kept not in (0, latest, day))
            del self._kept[oldest]
