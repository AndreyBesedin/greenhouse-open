"""What a plant takes from its local environment, and which way it responds
when one input changes."""

from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.tomato.organ.development import (
    DevelopmentParams,
    develop,
    emerged,
    grow,
)
from greenhouse_sim.biology.tomato.organ.environment import (
    LocalEnvironment,
    ResponseParams,
    co2_response,
    growth_factor,
    light_response,
)
from greenhouse_sim.biology.tomato.organ.topology import FruitStage, Plant, topology_problems
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.services import plants

PARAMS = DevelopmentParams()
RESPONSES = ResponseParams()
REFERENCE = plants.ENVIRONMENTS[plants.REFERENCE]
# Long enough for leaves to finish growing and the first fruits to ripen.
DAYS = 70


def _transplant() -> Plant:
    return develop(emerged("p01", PARAMS, seed=2), plants.TRANSPLANT_CD, PARAMS)


def _lived(change: dict[str, float], days: int = DAYS) -> Plant:
    """The transplant after these days in the reference environment, with
    one thing changed."""
    return grow(_transplant(), [REFERENCE.model_copy(update=change)] * days, PARAMS)


def _leaf_length(plant: Plant) -> float:
    return sum(phytomer.leaf.length_cm for phytomer in plant.stem.phytomers[:12])


def _fruit_mass(plant: Plant) -> float:
    return sum(
        flower.fruit.mass_g
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None and flower.fruit.stage == FruitStage.ATTACHED
    )


def _ripeness(plant: Plant) -> float:
    return sum(
        flower.fruit.ripeness
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None
    )


def test_light_and_co2_saturate_towards_the_reference_and_water_scales_growth() -> None:
    lights = [light_response(par, RESPONSES) for par in (0, 2, 5, 10, 20, 25, 40)]
    co2s = [co2_response(ppm, RESPONSES) for ppm in (0, 200, 400, 600, 800, 1200)]

    assert lights[0] == 0.0 and co2s[0] == 0.0
    assert lights == sorted(lights) and co2s == sorted(co2s)
    assert lights[-2:] == [1.0, 1.0] and co2s[-2:] == [1.0, 1.0]
    # Saturating: each mol adds less, the more light there already is.
    assert (lights[2] - lights[1]) / 3 > (lights[4] - lights[3]) / 10
    dry = REFERENCE.model_copy(update={"water_status": 0.5})
    assert growth_factor(dry, RESPONSES) == pytest.approx(0.5)
    assert growth_factor(REFERENCE, RESPONSES) == 1.0


def test_warmer_days_develop_a_plant_faster_and_ripen_its_fruit_sooner() -> None:
    cool, warm = _lived({"mean_temperature_c": 18.0}), _lived({"mean_temperature_c": 24.0})

    assert warm.thermal_time > cool.thermal_time
    assert len(warm.stem.phytomers) > len(cool.stem.phytomers)
    assert _ripeness(warm) > _ripeness(cool)


def test_days_below_the_base_temperature_develop_nothing() -> None:
    plant = _transplant()
    cold = _lived({"mean_temperature_c": PARAMS.base_temperature_c - 2}, days=10)

    assert cold == plant


def test_dimmer_days_grow_smaller_organs_at_the_same_pace() -> None:
    dim, bright = _lived({"par_mol_m2_day": 8.0}), _lived({})

    assert len(dim.stem.phytomers) == len(bright.stem.phytomers)
    assert _leaf_length(dim) < _leaf_length(bright)
    assert _fruit_mass(dim) < _fruit_mass(bright)
    assert topology_problems(dim) == []


def test_less_co2_or_water_grows_less() -> None:
    reference = _lived({})
    for change in ({"co2_ppm": 400.0}, {"water_status": 0.5}):
        poorer = _lived(change)
        assert _leaf_length(poorer) < _leaf_length(reference), change
        assert _fruit_mass(poorer) < _fruit_mass(reference), change


def test_better_than_the_reference_grows_no_more_than_the_potential() -> None:
    brighter = _lived({"par_mol_m2_day": 40.0, "co2_ppm": 1200.0})

    assert brighter == _lived({})


def test_growth_lost_in_poor_days_is_not_made_up_later() -> None:
    poor_then_good = grow(
        _lived({"par_mol_m2_day": 5.0}, days=20), [REFERENCE] * (DAYS - 20), PARAMS
    )
    always_good = _lived({})

    assert len(poor_then_good.stem.phytomers) == len(always_good.stem.phytomers)
    assert _leaf_length(poor_then_good) < _leaf_length(always_good)


def test_anything_that_says_each_plants_day_serves_as_its_environment() -> None:
    class Alternating:
        """Warm and cool on alternate days, recording what it was asked."""

        def __init__(self) -> None:
            self.asked: list[tuple[str, int]] = []

        def local(self, plant_id: str, day: int) -> LocalEnvironment:
            self.asked.append((plant_id, day))
            temperature = 24.0 if day % 2 == 0 else 16.0
            return REFERENCE.model_copy(update={"mean_temperature_c": temperature})

    source = Alternating()
    plant = grow(_transplant(), (source.local("p01", day) for day in range(10)), PARAMS)

    assert source.asked == [("p01", day) for day in range(10)]
    assert plant.thermal_time == pytest.approx(plants.TRANSPLANT_CD + 5 * 14.0 + 5 * 6.0)


def test_the_lab_keeps_its_plants_in_the_environment_asked_for() -> None:
    answer = respond("GET", "/api/plants/environments")
    cool = plants.structure(plants.LabRun(day=60, environment="cool_dim"))
    warm = plants.structure(plants.LabRun(day=60, environment="warm_bright"))

    assert answer.status == HTTPStatus.OK
    assert answer.body == {
        name: environment.model_dump(mode="json")
        for name, environment in plants.ENVIRONMENTS.items()
    }
    assert len(warm.stem.phytomers) > len(cool.stem.phytomers)
    assert _fruit_mass(warm) > _fruit_mass(cool)
    assert _ripeness(warm) > _ripeness(cool)


def test_two_environments_side_by_side_alternate_along_the_row_and_diverge() -> None:
    run = plants.LabRun(day=60, environment="cool_dim", versus="warm_bright")
    scene = SceneSnapshot.model_validate(
        respond("GET", "/api/plants/scene?day=60&environment=cool_dim&versus=warm_bright").body
    )
    by_plant = {
        e.properties["plant_id"]: e.properties["environment"]
        for e in scene.entities
        if "plant_id" in e.properties
    }
    row = {plant_id: plants.structure(run, plant_id) for plant_id in plants.plant_ids()}
    heights = {
        plant_id: sum(p.internode.length_cm for p in plant.stem.phytomers)
        for plant_id, plant in row.items()
    }

    for place, plant_id in enumerate(plants.plant_ids()):
        assert by_plant[plant_id] == ("warm_bright" if place % 2 else "cool_dim")
    cool, warm = plants.plant_ids()[0::2], plants.plant_ids()[1::2]
    assert min(heights[p] for p in warm) > max(heights[p] for p in cool)
    assert min(_ripeness(row[p]) for p in warm) > max(_ripeness(row[p]) for p in cool)


@pytest.mark.parametrize("query", ["environment=tropical", "versus=tropical"])
def test_an_environment_the_lab_does_not_have_is_refused(query: str) -> None:
    answer = respond("GET", f"/api/plants/scene?{query}")

    assert answer.status == HTTPStatus.BAD_REQUEST
    assert answer.body == {
        "error": "the plant lab has no environment 'tropical', "
        "only reference, warm_bright, cool_dim, dry"
    }
