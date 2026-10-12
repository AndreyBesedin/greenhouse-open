"""A run's crop, organ by organ, through its days (P09.3): each plant's day
from the house's air and its own light, crowns that grow, the run's crop
work, and the coupling recorded.

Most tests give a crop steady air and light of their own, so that a crop
grows months in a moment; the last ones grow the reference greenhouse's in
its own air and sunlight, for a day or two.
"""

from collections.abc import Callable, Sequence
from http import HTTPStatus
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.plant.organs import Fruit
from greenhouse_sim.biology.tomato.organ.actions import harvest_round
from greenhouse_sim.biology.tomato.organ.fruit import Maturity, maturity
from greenhouse_sim.biology.tomato.organ.geometry import stem_height_m
from greenhouse_sim.biology.tomato.organ.topology import HarvestFruit, Plant
from greenhouse_sim.biology.tomato.organ.transplants import transplant
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.clock import DAY_S, days_ended
from greenhouse_sim.core.crop import CropLight, CropWork, RunCrop
from greenhouse_sim.core.timeline import HARVEST_ROUND, RunProcesses, events
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.organs import FruitStage
from greenhouse_sim.domain.processes import Process
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import crop as crop_service
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.solar.plants import Crown

REFERENCE = SCENARIO_REGISTRY["reference_greenhouse"]
PLANTS: Final = ("p1", "p2", "p3")
SEED: Final = 42
# The plant lab's reference environment: all of the crop's potential growth.
WARM: Final = HouseAir(temperature_c=21.0, humidity_g_kg=8.0, co2_ppm=800.0)
COOL: Final = HouseAir(temperature_c=15.0, humidity_g_kg=8.0, co2_ppm=800.0)
BRIGHT_MOL: Final = 25.0
DIM_MOL: Final = 6.0
WEEKLY: Final = CropWork(harvest_every_days=7)
# In the warm air and bright light, the first fruit turns red in its
# twelfth week.
FIRST_RED_ROUND: Final = 84
SEASON_DAYS: Final = 120


class _Steady:
    """The same light on each crown all day, and through its day, `dimmer`
    plants taking less."""

    def __init__(self, crowns: Sequence[Crown], integral: float, dimmer: dict[str, float]):
        self.crowns = list(crowns)
        self.integral = integral
        self.dimmer = dimmer

    def par_at(self, time_s: float) -> dict[str, float]:
        return {crown.plant_id: self.integral / DAY_S * 1e6 for crown in self.crowns}

    def daily_light_integral(self, day: int = 0) -> dict[str, float]:
        return {
            crown.plant_id: self.dimmer.get(crown.plant_id, self.integral) for crown in self.crowns
        }


class _Asked:
    """What a crop asked of its air and light: the days, and each day's
    crowns' heights, by plant."""

    def __init__(self) -> None:
        self.air: list[int] = []
        self.crowns: dict[int, dict[str, float]] = {}


def _crop(
    air: HouseAir = WARM,
    integral: float = BRIGHT_MOL,
    *,
    dimmer: dict[str, float] | None = None,
    work: CropWork = WEEKLY,
    seed: int = SEED,
    asked: _Asked | None = None,
    air_on: Callable[[int], HouseAir] | None = None,
) -> RunCrop:
    """Three of the reference greenhouse's transplants, at its first three
    planting positions, in steady air and light."""
    record = _Asked() if asked is None else asked

    def day_air(day: int) -> HouseAir:
        record.air.append(day)
        return air if air_on is None else air_on(day)

    def light(day: int, crowns: Sequence[Crown]) -> CropLight:
        record.crowns[day] = {crown.plant_id: crown.height_m for crown in crowns}
        return _Steady(crowns, integral, dimmer or {})

    return RunCrop(
        [transplant(plant_id, seed) for plant_id in PLANTS],
        REFERENCE.layout.trainings(),
        REFERENCE.envelope,
        air=day_air,
        light=light,
        work=work,
        days=SEASON_DAYS,
    )


def _organ_length_cm(plant: Plant) -> float:
    """How long the plant's internodes and leaves are, together."""
    return sum(getattr(organ, "length_cm", 0.0) for _, _, _, organ in plant.organs())


def _red(plant: Plant) -> list[str]:
    """The red fruits on the plant, from its lowest truss up."""
    return [
        organ.fruit_id
        for _, _, _, organ in plant.organs()
        if isinstance(organ, Fruit)
        and organ.stage == FruitStage.ATTACHED
        and maturity(organ.ripeness) == Maturity.RED
    ]


def test_the_crop_starts_as_its_transplants_and_lives_a_day_at_each_midnight() -> None:
    crop = _crop()

    assert crop.plants_on(0) == tuple(transplant(plant_id, SEED) for plant_id in PLANTS)
    first = crop.plants_on(1)
    # A day at 21 °C, 11 °Cd above the crop's base.
    assert [
        p.thermal_time - t.thermal_time for p, t in zip(first, crop.plants_on(0), strict=True)
    ] == (pytest.approx([11.0] * len(PLANTS)))
    assert days_ended(0.0) == 0
    assert days_ended(DAY_S - 1.0) == 0
    assert days_ended(DAY_S) == 1
    assert days_ended(2.5 * DAY_S) == 2


def test_each_plants_day_is_the_houses_air_and_its_own_light() -> None:
    crop = _crop(dimmer={"p2": DIM_MOL})

    assert crop.local("p1", 3) == LocalEnvironment(
        mean_temperature_c=21.0, par_mol_m2_day=BRIGHT_MOL, co2_ppm=800.0, water_status=1.0
    )
    assert crop.local("p2", 3) == LocalEnvironment(
        mean_temperature_c=21.0, par_mol_m2_day=DIM_MOL, co2_ppm=800.0
    )
    assert crop.environments("p1", 4) == [crop.local("p1", day) for day in range(4)]
    with pytest.raises(LookupError, match="no plant"):
        crop.local("nobody", 0)
    with pytest.raises(ValueError, match="days 0 to 119"):
        crop.local("p1", SEASON_DAYS)
    with pytest.raises(ValueError, match="days 0 to 120"):
        crop.plants_on(SEASON_DAYS + 1)


def test_a_plant_in_more_light_grows_more() -> None:
    crop = _crop(dimmer={"p2": DIM_MOL})
    bright = _crop()
    day = 30

    dim_plant = crop.plants_on(day)[1]
    bright_plant = bright.plants_on(day)[1]

    # The same thermal time, so the same organs, each grown less.
    assert dim_plant.thermal_time == bright_plant.thermal_time
    assert [o for _, o, _, _ in dim_plant.organs()] == [o for _, o, _, _ in bright_plant.organs()]
    assert _organ_length_cm(dim_plant) < 0.8 * _organ_length_cm(bright_plant)
    # Its neighbours in the bright light grow as they would without it.
    assert crop.plants_on(day)[0] == bright.plants_on(day)[0]


def test_a_warmer_house_develops_the_crop_faster() -> None:
    warm = _crop(WARM).plants_on(30)
    cool = _crop(COOL).plants_on(30)

    for warmer, cooler in zip(warm, cool, strict=True):
        assert warmer.thermal_time - cooler.thermal_time == pytest.approx(30 * (21.0 - 15.0))
        assert len(warmer.stem.phytomers) > len(cooler.stem.phytomers)


def test_the_same_seed_grows_the_same_crop_and_another_another() -> None:
    assert _crop().plants_on(20) == _crop().plants_on(20)
    assert _crop(seed=7).plants_on(20) != _crop().plants_on(20)


def test_each_days_light_is_read_with_the_crowns_as_tall_as_the_plants_stand() -> None:
    asked = _Asked()
    crop = _crop(asked=asked)

    crop.plants_on(20)

    assert sorted(asked.crowns) == list(range(20))
    for day in (0, 10, 19):
        plants = crop.plants_on(day)
        assert asked.crowns[day] == {p.plant_id: stem_height_m(p) for p in plants}
        assert [crown.height_m for crown in crop.crowns_on(day)] == [
            stem_height_m(p) for p in plants
        ]
    # The crowns grow: a taller crop shades more of its neighbours.
    assert all(asked.crowns[19][plant] > asked.crowns[0][plant] for plant in PLANTS)


def test_a_day_is_worked_out_once_and_any_day_lived_again_from_what_was_kept() -> None:
    asked = _Asked()
    crop = _crop(asked=asked)

    later = crop.plants_on(40)
    earlier = crop.plants_on(12)
    again = crop.plants_on(40)
    crop.local("p3", 25)

    assert asked.air == list(range(40))
    assert earlier == _crop().plants_on(12)
    assert again == later


def test_a_harvest_round_picks_every_red_fruit_each_a_harvest_of_its_own() -> None:
    plant = _crop(work=CropWork()).plants_on(FIRST_RED_ROUND)[0]
    red = _red(plant)
    assert red

    harvested = harvest_round(plant)

    assert _red(harvested) == []
    picked = harvested.history[len(plant.history) :]
    assert [event.action for event in picked] == [HarvestFruit(fruit_id=f) for f in red]
    assert all(event.applied and event.harvested_g > 0 for event in picked)
    assert harvest_round(harvested) == harvested


def test_the_crop_is_harvested_every_week_and_each_plant_keeps_what_was_picked() -> None:
    crop = _crop()
    unworked = _crop(work=CropWork())

    plants = crop.plants_on(FIRST_RED_ROUND)
    before = crop.plants_on(FIRST_RED_ROUND - 1)

    assert all(_red(plant) == [] for plant in plants)
    assert any(_red(plant) for plant in before)
    for plant, same in zip(plants, unworked.plants_on(FIRST_RED_ROUND), strict=True):
        picked = [event.action.fruit_id for event in plant.history]  # type: ignore[union-attr]
        assert picked
        assert set(picked) <= {o for k, o, _, _ in same.organs() if k == "fruit"}
    # Only a round's day starts with a harvest.
    assert [WEEKLY.harvests_on(day) for day in (0, 6, 7, 8, 14, 84)] == [
        False,
        False,
        True,
        False,
        True,
        True,
    ]


def test_a_crop_takes_over_the_days_another_lived_in_the_same_air() -> None:
    first_asked, second_asked = _Asked(), _Asked()
    first = _crop(asked=first_asked)
    first.plants_on(10)
    # The second run's air differs from its sixth day on.
    second = _crop(asked=second_asked, air_on=lambda day: WARM if day < 6 else COOL)

    second.carry_on_from(first, 6)
    shared = second.plants_on(6)
    later = second.plants_on(10)

    assert second_asked.air == list(range(6, 10))
    assert shared == first.plants_on(6)
    assert later != first.plants_on(10)
    assert second.local("p1", 5) == first.local("p1", 5)


def test_the_timeline_lists_each_harvest_round_after_the_plants_day() -> None:
    run = RunProcesses(
        schedule=Schedule(),
        air_step_s=None,
        plants=list(PLANTS),
        sensors=[],
        cameras=[],
        crop_work=WEEKLY,
    )

    found = events(run, 6 * DAY_S, 7 * DAY_S)

    at_midnight = [(e.process, e.subject, e.kind) for e in found if e.time_s == 7 * DAY_S]
    assert at_midnight == [
        *((Process.PLANTS, plant, "day 6") for plant in PLANTS),
        *((Process.PLANTS, plant, HARVEST_ROUND) for plant in PLANTS),
    ]
    assert [e for e in events(run, 0.0, 6 * DAY_S) if e.kind == HARVEST_ROUND] == []


# The reference greenhouse's own crop, in its own air and sunlight.
FIRST_PLANT = "reference_greenhouse_plant_001"


def _body(path: str) -> dict[str, Any]:
    response = respond("GET", path)
    assert response.status == HTTPStatus.OK, response.body
    assert isinstance(response.body, dict)
    return response.body


def test_the_reference_greenhouse_grows_its_crop_organ_by_organ() -> None:
    assert REFERENCE.crop_model == CropModel.ORGAN
    assert REFERENCE.crop_work == CropWork(
        harvest_every_days=7, lower_every_days=7, head_room_m=0.3
    )
    others = [s for s in SCENARIO_REGISTRY.values() if s.greenhouse_id != "reference_greenhouse"]
    assert all(other.crop_model == CropModel.SIMPLE for other in others)

    refused = respond("GET", "/api/scenarios/climate_box/crop?t=0")
    assert refused.status == HTTPStatus.NOT_FOUND
    assert refused.body == {
        "error": "climate_box grows its crop with the simple daily model, not by organ"
    }


def test_before_its_first_day_its_scene_draws_its_transplants_as_its_crop_does() -> None:
    scene = _body("/api/scenarios/reference_greenhouse/scene")
    crop = _body("/api/scenarios/reference_greenhouse/crop")

    organs = [entity for entity in scene["entities"] if "organ_id" in entity["properties"]]
    assert organs == crop["entities"]
    assert crop["simulated_day"] == 0


def test_its_crop_on_a_moments_day_has_lived_the_days_ended_by_then() -> None:
    scene = _body(f"/api/scenarios/reference_greenhouse/crop?t={1.5 * DAY_S:.0f}")
    plant = _body(f"/api/scenarios/reference_greenhouse/crop/{FIRST_PLANT}?t={1.5 * DAY_S:.0f}")
    crop = crop_service.run_crop("reference_greenhouse")

    assert scene["simulated_day"] == 1
    drawn = {entity["properties"]["plant_id"] for entity in scene["entities"]}
    assert drawn == set(plant_ids(REFERENCE))
    assert all("organ_id" in entity["properties"] for entity in scene["entities"])
    assert plant["days"] == 1
    assert Plant.model_validate(plant["structure"]) == crop.plants_on(1)[0]
    assert [LocalEnvironment.model_validate(e) for e in plant["environments"]] == [
        crop.local(FIRST_PLANT, 0)
    ]
    missing = respond("GET", "/api/scenarios/reference_greenhouse/crop/nobody?t=0")
    assert missing.status == HTTPStatus.NOT_FOUND


def test_its_plants_share_the_houses_air_each_in_its_own_light() -> None:
    crop = crop_service.run_crop("reference_greenhouse")
    days = [crop.local(plant_id, 0) for plant_id in plant_ids(REFERENCE)]
    house = _body("/api/scenarios/reference_greenhouse/climate/house?t=86400")
    light = _body("/api/scenarios/reference_greenhouse/climate/plants?t=43200")

    assert {(day.mean_temperature_c, day.co2_ppm, day.water_status) for day in days} == {
        (days[0].mean_temperature_c, 420.0, 1.0)
    }
    # The house's mean through the day, as its minutes have it.
    minutes = house["controlled"]["temperature_c"]
    assert days[0].mean_temperature_c == pytest.approx(sum(minutes) / len(minutes), abs=0.01)
    assert len({day.par_mol_m2_day for day in days}) > 1
    assert light["daily_light_integral_mol_m2_d"] == {
        plant_id: day.par_mol_m2_day
        for plant_id, day in zip(plant_ids(REFERENCE), days, strict=True)
    }


def test_a_heated_house_develops_its_crop_faster() -> None:
    # Without its own schedule, unheated, and with the heater on throughout.
    cold = _body(f"/api/scenarios/reference_greenhouse/crop/{FIRST_PLANT}?t={DAY_S:.0f}&daily=none")
    heated = _body(
        f"/api/scenarios/reference_greenhouse/crop/{FIRST_PLANT}?t={DAY_S:.0f}&daily=none"
        "&set=heater:1"
    )

    warmer = heated["environments"][0]["mean_temperature_c"]
    colder = cold["environments"][0]["mean_temperature_c"]
    assert warmer > colder + 3.0
    gained = heated["structure"]["thermal_time"] - cold["structure"]["thermal_time"]
    assert gained == pytest.approx(warmer - colder)


def test_a_crop_takes_a_checkpoints_days_only_with_every_day_lived_before() -> None:
    source = _crop()
    plants, lived = source.plants_on(5), source.lived_through(5)
    asked = _Asked()
    seeded = _crop(asked=asked)

    seeded.seed(5, plants, lived)

    assert seeded.plants_on(5) == plants
    assert seeded.environments("p1", 5) == source.environments("p1", 5)
    assert seeded.plants_on(6) == source.plants_on(6)
    assert asked.air == [5]
    with pytest.raises(ValueError, match="has lived 5 days, not 4"):
        _crop().seed(5, plants, lived[:4])
