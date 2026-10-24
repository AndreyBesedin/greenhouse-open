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

The crop's days are worked out in order, and what each plant experienced on
each is kept, so that its days can be listed and its plants on any day
lived again from them, without the air or the light. Its plants are kept on
its first day, on the latest worked out, and on the few last asked for. A
crop may take over another's days, up to the first on which their runs'
air, or their own crop actions, differ (`carry_on_from`).
"""

import threading
import weakref
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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
from greenhouse_sim.climate.run import LOOK_AGAIN_S
from greenhouse_sim.core.crop_actions import CarriedOut, CropAction, CropEffect, carry_out
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


class RunCrop[PlantT: CropPlant]:
    """A run's crop of `transplants` through its `days`, grown by `rung`,
    the first plant trained as the first of `trainings` says in `envelope`,
    and so on: each day in `air` and its own `light`, worked as `work` says,
    and then as the run's own crop actions on that day ask (`planned`, by
    day). It is the plant model's environment for its plants (`local`). A
    `watch` times the parts of each day it works out, for a benchmark."""

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
        self.days = days
        self.work = work
        self.rung = rung
        self._watch = watch
        self._plant_ids = [plant.plant_id for plant in transplants]
        self._planned = {day: tuple(acts) for day, acts in (planned or {}).items() if acts}
        for day, acts in self._planned.items():
            if not 0 < day <= days:
                raise ValueError(f"a run's crop is worked on days 1 to {days}, not {day}")
            for action in acts:
                if action.plant_id not in self._plant_ids:
                    raise ValueError(f"a run's crop has no plant {action.plant_id!r}")
        # What the planned crop actions of each day worked out did.
        self._done: dict[int, DayWork] = {}
        self._trainings = list(trainings)
        self._envelope = envelope
        self._air = air
        self._light = light
        # What each plant experienced on each day worked out, from the first.
        self._lived: list[dict[str, LocalEnvironment]] = []
        # The plants on the days kept: the first, the latest worked out, and
        # the last asked for.
        self._kept: OrderedDict[int, tuple[PlantT, ...]] = OrderedDict({0: tuple(transplants)})
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
        self._sources: list[tuple[weakref.ref[RunCrop[PlantT]], int]] = []

    def _checked(self, day: int, last: int) -> None:
        if not 0 <= day <= last:
            raise ValueError(f"a run's crop has days 0 to {last}, not {day}")

    def plants_on(self, day: int) -> tuple[PlantT, ...]:
        """The crop on the run's day `day`, from 0 to its days: its plants
        once they have lived the days before it, after that day's crop
        work."""
        self._checked(day, self.days)
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
                plants = self._lived_through(start, day)
            finally:
                with self._kept_changed:
                    self._stretch = None
                    self._kept_changed.notify_all()
            self._keep(day, plants)
            return plants

    def _lived_through(self, start: int, day: int) -> tuple[PlantT, ...]:
        plants = self._kept[start]
        for lived in range(start, day):
            plants = self._next_day(lived, plants)
        return plants

    def _next_day(self, lived: int, plants: tuple[PlantT, ...]) -> tuple[PlantT, ...]:
        """The crop on the day after `lived`, `plants` on it: once they have
        lived it, after the next day's crop work and its own crop actions."""
        environments = self._day(lived, plants)
        with timed(self._watch, PLANTS_DAYS):
            plants = tuple(
                self._worked(
                    lived + 1,
                    self.rung.live_day(plant, environments[plant.plant_id]),
                    training,
                )
                for plant, training in zip(plants, self._trainings, strict=False)
            )
            planned = self._planned.get(lived + 1)
            if planned:
                plants = self._carried_out(lived + 1, plants, planned)
        return plants

    def worked_on(self, day: int) -> DayWork | None:
        """What the run's own crop actions on its day `day` did, from 0 to
        its days, the crop worked through that day if it has not been; None
        if it has none that day."""
        self._checked(day, self.days)
        if day not in self._planned:
            return None
        with self._working:
            if day not in self._done:
                self.plants_on(day)
            if day not in self._done:
                # Its plants on that day were taken over, or given, rather
                # than worked out here: work the day out again, the same.
                self._next_day(day - 1, self.plants_on(day - 1))
            return self._done[day]

    def local(self, plant_id: str, day: int) -> LocalEnvironment:
        """What a plant experienced on the run's day `day`, from 0 to its
        last."""
        self._checked(day, self.days - 1)
        with self._working:
            self._take_over(day + 1)
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
        plants: Sequence[CropPlant],
        lived: Sequence[dict[str, LocalEnvironment]],
    ) -> None:
        """Take `plants` as the crop on the run's `day`, and `lived` as what
        they experienced on each day before it, from a checkpoint of the
        same run (P09.5): later days carry on from them. Refused if they are
        not its model's plants."""
        self._checked(day, self.days)
        if len(lived) != day:
            raise ValueError(f"a crop on day {day} has lived {day} days, not {len(lived)}")
        if not self._its_own(plants):
            raise ValueError(f"a crop of {self.rung.plant_type.__name__} plants takes no others")
        with self._working, self._keeping:
            if len(self._lived) < day:
                self._lived = list(lived)
            self._kept.setdefault(day, tuple(plants))

    def _its_own(self, plants: Sequence[CropPlant]) -> TypeIs[Sequence[PlantT]]:
        return all(isinstance(plant, self.rung.plant_type) for plant in plants)

    def crowns_on(self, day: int) -> list[Crown]:
        """The plants' crowns on the run's day `day`, each as tall as its
        plant's stem stands."""
        return self._crowns(self.plants_on(day))

    def light_on(self, day: int) -> CropLight:
        """The light on the crop on the run's day `day`, from 0 to its last,
        its crowns as tall as its plants stand that day."""
        self._checked(day, self.days - 1)
        return self._light(day, self.crowns_on(day))

    def carry_on_from(self, other: RunCrop[PlantT], days: int) -> None:
        """Take over what `other` worked out of the run's first `days` days:
        what its plants experienced on them, and its plants kept on those
        days and the next; and what it works out of them later, as this crop
        works its own days on. Only another crop of the same scenario, in a
        run whose air is the same through those days, and whose own crop
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
                        (kept_day, plants)
                        for kept_day, plants in other._kept.items()
                        if kept_day <= through
                    ]
                    ahead = max(len(self._lived), len(lived))
                    waiting = other._working_through(ahead, through)
                    if waiting:
                        other._kept_changed.wait(LOOK_AGAIN_S)
                with self._keeping:
                    if len(self._lived) < len(lived):
                        self._lived = lived
                    for kept_day, plants in kept:
                        if kept_day <= len(self._lived):
                            self._kept.setdefault(kept_day, plants)
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

    def _day(self, day: int, plants: tuple[PlantT, ...]) -> dict[str, LocalEnvironment]:
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
        with self._keeping:
            self._lived.append(environments)
        return environments

    def _worked(self, day: int, plant: PlantT, training: Training) -> PlantT:
        """The plant after the crop work that starts the run's day `day`, its
        crop actions carried out in order (`CropWork.actions_on`); a plant
        that hangs from no wire is not lowered."""
        for action in self.work.actions_on(day, plant.plant_id):
            plant = self.rung.carry_out(plant, action, training).plant
        return plant

    def _carried_out(
        self, day: int, plants: tuple[PlantT, ...], planned: Sequence[CropAction]
    ) -> tuple[PlantT, ...]:
        """The crop after the run's own crop actions on its day `day`, in
        their order, `plants` once its crop work was done; what each did
        kept."""
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
        with self._keeping:
            self._done[day] = DayWork(tuple(done), work_ends)
        return tuple(worked)

    def _crowns(self, plants: Sequence[PlantT]) -> list[Crown]:
        return crowns(self.rung, plants, self._trainings, self._envelope)

    def _keep(self, day: int, plants: tuple[PlantT, ...]) -> None:
        with self._keeping:
            self._kept[day] = plants
            self._kept.move_to_end(day)
            self._bounded(day)

    def _bounded(self, day: int) -> None:
        """Drop the days kept longest ago beyond `KEPT_DAYS` and two: never
        the first, the latest or `day`. Called with `_keeping` held."""
        latest = max(self._kept)
        while len(self._kept) > KEPT_DAYS + 2:
            oldest = next(kept for kept in self._kept if kept not in (0, latest, day))
            del self._kept[oldest]
