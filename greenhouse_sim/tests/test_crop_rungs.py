"""Every model of the run's crop honours the crop part's contract
(`greenhouse_sim.core.crop.CropRung`, decision 0035, P14.3).

The tests take the rungs as parameters, so a new crop model joins by being
added to the list below, whose annotation makes mypy check that it
satisfies the protocol.
"""

from collections.abc import Sequence
from typing import Any

import pytest
from greenhouse_protocol.actions import Harvest, HarvestScope, Lower, RemoveLeaf
from greenhouse_protocol.outcome import Harvested, Lowered
from pydantic import TypeAdapter

from greenhouse_sim.biology.crop_contract import CropRung
from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.crop import CropLight, CropWork, OrganRung, RunCrop
from greenhouse_sim.core.simple_crop import SimplePlant, SimpleRung
from greenhouse_sim.domain.crop import FruitStatus
from greenhouse_sim.environment.simple import SimpleEnvironmentModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.solar.plants import Crown
from greenhouse_sim.world.training import Training
from greenhouse_sim.world_builder import advance_world, initialize_world

CONFIG = SCENARIO_REGISTRY["climate_box"]
SEED = CONFIG.random_seed
RUNGS: list[CropRung[Any]] = [OrganRung(SEED), SimpleRung(CONFIG)]
PLANTS = plant_ids(CONFIG)[:3]
# A day as a greenhouse's might be, the same every day.
STEADY = LocalEnvironment(mean_temperature_c=22.0, par_mol_m2_day=20.0, co2_ppm=600.0)
# Long enough for the simple crop's trusses, fruit and ripe fruit.
DAYS = 40
TRAINING = CONFIG.layout.trainings()[0]
# A plant hanging from a wire 1.5 m above its foot.
WIRED = Training(position=TRAINING.position, path=TRAINING.path, wire_m=1.5)


def _name(rung: object) -> str:
    return type(rung).__name__


def _lived(rung: CropRung[Any], plant: Any, days: int = DAYS) -> list[Any]:
    """The plant on each day, from its first, living each in `STEADY`."""
    days_lived = [plant]
    for _ in range(days):
        days_lived.append(rung.live_day(days_lived[-1], STEADY))
    return days_lived


def _dumped(rung: CropRung[Any], plant: Any) -> bytes:
    return TypeAdapter(rung.plant_type).dump_json(plant)


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_rung_starts_and_lives_a_plant_the_same_every_time(rung: CropRung[Any]) -> None:
    first = _lived(rung, rung.transplant(PLANTS[0]))
    again = _lived(rung, rung.transplant(PLANTS[0]))

    assert [_dumped(rung, plant) for plant in first] == [_dumped(rung, plant) for plant in again]
    assert _dumped(rung, first[-1]) != _dumped(rung, first[0])


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_plants_day_is_its_own_whatever_lives_beside_it(rung: CropRung[Any]) -> None:
    alone = _lived(rung, rung.transplant(PLANTS[0]), 10)
    plant, other = rung.transplant(PLANTS[0]), rung.transplant(PLANTS[1])
    beside = [plant]
    for _ in range(10):
        other = rung.live_day(other, STEADY)
        beside.append(rung.live_day(beside[-1], STEADY))

    assert [_dumped(rung, p) for p in beside] == [_dumped(rung, p) for p in alone]
    # Each plant is drawn by its own identity.
    assert _dumped(rung, other) != _dumped(rung, beside[-1])


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_rung_leaves_the_plant_it_is_given_as_it_was(rung: CropRung[Any]) -> None:
    plant = _lived(rung, rung.transplant(PLANTS[0]))[-1]
    before = _dumped(rung, plant)

    rung.live_day(plant, STEADY)
    rung.carry_out(plant, Harvest(plant_id=plant.plant_id, scope=HarvestScope.RIPE), WIRED)
    rung.carry_out(plant, Lower(plant_id=plant.plant_id, to_head_room_m=0.3), WIRED)

    assert _dumped(rung, plant) == before


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_rung_keeps_a_plants_identifier_through_its_days_and_its_work(
    rung: CropRung[Any],
) -> None:
    days = _lived(rung, rung.transplant(PLANTS[2]))
    harvested = rung.carry_out(
        days[-1], Harvest(plant_id=PLANTS[2], scope=HarvestScope.RIPE), WIRED
    )
    lowered = rung.carry_out(harvested.plant, Lower(plant_id=PLANTS[2], by_cm=10.0), WIRED)

    assert {plant.plant_id for plant in [*days, harvested.plant, lowered.plant]} == {PLANTS[2]}


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_rungs_plants_survive_a_json_round_trip(rung: CropRung[Any]) -> None:
    """As a checkpoint keeps them."""
    adapter = TypeAdapter(rung.plant_type)
    for plant in _lived(rung, rung.transplant(PLANTS[0]))[::10]:
        assert adapter.validate_json(adapter.dump_json(plant)) == plant


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_harvest_round_is_done_even_when_nothing_is_ripe(rung: CropRung[Any]) -> None:
    plant = rung.transplant(PLANTS[0])

    done = rung.carry_out(plant, Harvest(plant_id=PLANTS[0], scope=HarvestScope.RIPE), TRAINING)

    assert done.refusal is None
    assert done.effect == Harvested(fruit_count=0, fresh_mass_g=0.0)


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_plant_on_no_wire_is_not_lowered_to_a_head_room_under_one(rung: CropRung[Any]) -> None:
    plant = _lived(rung, rung.transplant(PLANTS[0]))[-1]

    refused = rung.carry_out(plant, Lower(plant_id=PLANTS[0], to_head_room_m=0.3), None)

    assert refused.refusal == f"{PLANTS[0]} hangs from no wire"
    assert refused.effect is None


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_crown_stands_from_its_foot_as_its_plant_grows(rung: CropRung[Any]) -> None:
    heights = [rung.crown(plant, TRAINING)[1] for plant in _lived(rung, rung.transplant(PLANTS[0]))]

    assert all(height >= 0.0 for height in heights)
    assert heights[-1] > heights[0]


class _Steady:
    """Light the same on every crown, every day."""

    def __init__(self, crowns: Sequence[Crown]) -> None:
        self.crowns = crowns

    def par_at(self, time_s: float) -> dict[str, float]:
        return {crown.plant_id: 400.0 for crown in self.crowns}

    def daily_light_integral(self, day: int = 0) -> dict[str, float]:
        return {crown.plant_id: 20.0 for crown in self.crowns}


def _crop(rung: CropRung[Any], days: int = 12) -> RunCrop[Any]:
    def light(_day: int, crowns: Sequence[Crown]) -> CropLight:
        return _Steady(crowns)

    return RunCrop(
        [rung.transplant(plant_id) for plant_id in PLANTS],
        CONFIG.layout.trainings(),
        CONFIG.envelope,
        rung=rung,
        air=lambda _: HouseAir(temperature_c=22.0, humidity_g_kg=8.0, co2_ppm=600.0),
        light=light,
        work=CropWork(harvest_every_days=7),
        days=days,
    )


@pytest.mark.parametrize("rung", RUNGS, ids=_name)
def test_a_run_of_each_rung_carries_on_from_a_checkpoint_of_its_own_plants(
    rung: CropRung[Any],
) -> None:
    crop = _crop(rung)
    seeded = _crop(rung)
    seeded.seed(5, crop.plants_on(5), crop.lived_through(5))

    assert seeded.plants_on(12) == crop.plants_on(12)
    other = next(other for other in RUNGS if type(other) is not type(rung))
    with pytest.raises(ValueError, match="plants takes no others"):
        _crop(rung).seed(0, [other.transplant(PLANTS[0])], [])


def test_the_simple_rung_grows_a_plant_as_the_engine_does_at_the_same_temperatures() -> None:
    """The simple model keeps its numbers as a rung of the run (decision
    0035): given each day's temperature the engine's air drifts to, it grows
    the engine's plants."""
    rung = SimpleRung(CONFIG)
    world = initialize_world(CONFIG, PLANTS)
    plants = [rung.transplant(plant_id) for plant_id in PLANTS]
    environment = SimpleEnvironmentModel()
    for day in range(1, DAYS + 1):
        air = environment.advance(world.environment, CONFIG, day)
        world = advance_world(world, CONFIG, day)
        assert world.environment == air
        lived = LocalEnvironment(
            mean_temperature_c=air.air_temperature_c, par_mol_m2_day=0.0, co2_ppm=0.0
        )
        plants = [rung.live_day(plant, lived) for plant in plants]

    assert [plant.plant for plant in plants] == world.plants
    assert any(fruit.status == FruitStatus.RIPE for fruit in _fruits(plants[0]))


def _fruits(plant: SimplePlant) -> list[Any]:
    return [fruit for truss in plant.plant.trusses for fruit in truss.fruits]


def test_the_simple_crops_harvest_round_picks_its_ripe_fruit() -> None:
    rung = SimpleRung(CONFIG)
    plant = _lived(rung, rung.transplant(PLANTS[0]))[-1]
    ripe = [fruit for fruit in _fruits(plant) if fruit.status == FruitStatus.RIPE]

    done = rung.carry_out(plant, Harvest(plant_id=PLANTS[0], scope=HarvestScope.RIPE), None)

    assert ripe
    assert done.effect == Harvested(
        fruit_count=len(ripe), fresh_mass_g=sum(fruit.mass_g for fruit in ripe)
    )
    assert not [fruit for fruit in _fruits(done.plant) if fruit.status == FruitStatus.RIPE]
    assert done.plant.plant.cumulative_harvest_g == pytest.approx(done.effect.fresh_mass_g)


def test_the_simple_crop_is_lowered_to_its_head_room_under_its_wire() -> None:
    rung = SimpleRung(CONFIG)
    plant = _lived(rung, rung.transplant(PLANTS[0]))[-1]
    low = Training(position=TRAINING.position, path=TRAINING.path, wire_m=0.7)
    assert plant.standing_cm() > 40.0

    lowered = rung.carry_out(plant, Lower(plant_id=PLANTS[0], to_head_room_m=0.3), low)
    again = rung.carry_out(lowered.plant, Lower(plant_id=PLANTS[0], to_head_room_m=0.3), low)

    assert lowered.plant.standing_cm() == pytest.approx(40.0)
    assert isinstance(lowered.effect, Lowered)
    assert lowered.effect.by_cm == pytest.approx(plant.standing_cm() - 40.0)
    assert again.effect == Lowered(by_cm=0.0)


@pytest.mark.parametrize(
    ("action", "said"),
    [
        (RemoveLeaf(plant_id=PLANTS[0], leaf_id="a_leaf"), "has no leaves"),
        (Lower(plant_id=PLANTS[0], by_internodes=1), "has no internodes"),
        (
            Harvest(plant_id=PLANTS[0], scope=HarvestScope.FRUIT, organ_id="a_fruit"),
            "is harvested by its ripe fruit",
        ),
    ],
)
def test_the_simple_crop_refuses_an_action_on_a_part_its_stem_is_not_built_of(
    action: Any, said: str
) -> None:
    rung = SimpleRung(CONFIG)
    plant = rung.transplant(PLANTS[0])

    refused = rung.carry_out(plant, action, WIRED)

    assert refused.refusal == f"{PLANTS[0]} of the simple crop {said}"
    assert refused.plant == plant
