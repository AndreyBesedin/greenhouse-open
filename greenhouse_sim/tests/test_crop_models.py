"""Each crop model is registered with all that tells it apart (decisions
0055 and 0062, P14.6): the registry's name, version and parameters, and,
under the same name, what it declares, which every registration answers as
the services take it, and which no service asks of it by its name."""

import re
from pathlib import Path
from typing import Any, Final

import pytest

import greenhouse_sim
from greenhouse_sim.biology.area_contract import HourDrivers, StepCourse
from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.core.area_crop import AreaInstance
from greenhouse_sim.core.drivers import HOUSE_HOURS
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import ReducedTomgroCrop
from greenhouse_sim.scenarios.registry import MODELS
from greenhouse_sim.scene.snapshot import SceneEntityKind
from greenhouse_sim.services.crop_models import (
    CROP_MODELS,
    CropActions,
    CropRegistration,
    registration,
)
from greenhouse_sim.services.runs import CROP_KINDS
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.units import HOURS_A_DAY
from greenhouse_sim.world.scopes import row_scopes

CONFIG = SCENARIO_REGISTRY["climate_box"]
PLANTS = plant_ids(CONFIG)[:2]
STEADY = LocalEnvironment(mean_temperature_c=22.0, par_mol_m2_day=20.0, co2_ppm=600.0)
# Long enough for the simple crop's fruit, and the organ crop's first truss.
DAYS = 40


def test_every_crop_model_of_the_registry_is_registered_for_the_services() -> None:
    assert set(CROP_MODELS) == set(MODELS[Part.CROP])
    for name, registered in CROP_MODELS.items():
        assert registered.name == name
    assert registration(CONFIG) is CROP_MODELS[CONFIG.crop.kind]


def test_each_crop_model_grows_single_plants_or_an_area() -> None:
    """One of the two, as it declares (decision 0062)."""
    assert {
        name: (each.plants is None, each.area is None) for name, each in CROP_MODELS.items()
    } == {
        "organ": (False, True),
        "simple": (False, True),
        "reduced_tomgro": (True, False),
    }


# The registrations of the models that grow single plants.
GROWN_BY_PLANT: Final = [each for each in CROP_MODELS.values() if each.plants is not None]


def _grown(registered: CropRegistration[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    """Its transplants after `DAYS` days in `STEADY`, and what they lived."""
    assert registered.plants is not None
    rung = registered.plants.rung(CONFIG)
    plants = [rung.transplant(plant_id) for plant_id in PLANTS]
    for _ in range(DAYS):
        plants = [rung.live_day(plant, STEADY) for plant in plants]
    return plants, [dict.fromkeys(PLANTS, STEADY) for _ in range(DAYS)]


@pytest.mark.parametrize("registered", GROWN_BY_PLANT, ids=[each.name for each in GROWN_BY_PLANT])
def test_a_registration_answers_what_the_services_ask_of_a_crop_model(
    registered: CropRegistration[Any],
) -> None:
    plants, lived = _grown(registered)
    assert registered.plants is not None

    # Its state, as a checkpoint keeps and reads it back, plausible on its
    # day, and not on another.
    state = registered.state.model_validate({"plants": plants, "lived": lived})
    assert registered.state.model_validate_json(state.model_dump_json()) == state
    assert registered.implausible(state, DAYS) == []
    # Drawn, each plant in the scene; measured as a walk finds it.
    drawn = registered.plants.drawn(plants, CONFIG)
    assert {entity.properties.get("plant_id", entity.entity_id) for entity in drawn} == set(PLANTS)
    measured = [registered.plants.measured(plant) for plant in plants]
    assert [plant.plant_id for plant in measured] == PLANTS
    assert all(plant.height_cm > 0 and plant.fruits >= plant.ripe >= 0 for plant in measured)
    # A plant has picked nothing since itself; a replay counts its organs.
    assert [registered.plants.picked(plant, plant, None) for plant in plants] == [(0, 0.0)] * 2
    organs, thermal_cd = registered.plants.probed(plants)
    assert organs >= 0 and thermal_cd >= 0.0


def test_the_organs_registration_finds_what_no_run_of_it_reaches() -> None:
    plants, lived = _grown(CROP_MODELS["organ"])
    state = CROP_MODELS["organ"].state.model_validate({"plants": plants, "lived": lived[1:]})

    (problem, *_) = CROP_MODELS["organ"].implausible(state, DAYS)
    assert "thermal time" in problem


def test_only_the_organ_crop_takes_the_runs_own_crop_actions() -> None:
    """As the run carries a plan's crop actions out (P13.5): every kind of
    them a plan may ask."""
    assert {name: each.crop_actions for name, each in CROP_MODELS.items()} == {
        "organ": CropActions(CROP_KINDS),
        "simple": None,
        "reduced_tomgro": None,
    }


# The climate box, its rows growing Reduced-State TOMGRO.
TOMGRO_BOX: Final = ScenarioConfig.model_validate(
    CONFIG.model_dump() | {"crop_model": "reduced_tomgro", "crop": {"kind": "reduced_tomgro"}}
)


def test_reduced_tomgros_registration_answers_what_the_services_ask_of_it() -> None:
    """A model grown by area (decision 0062): its rung, its driver profile,
    its state as a checkpoint keeps it, plausible, and drawn as each row's
    canopy, a proxy, rather than plants."""
    registered = registration(TOMGRO_BOX)
    assert registered.area is not None
    rung = registered.area.rung(TOMGRO_BOX)
    profile = registered.area.profile(TOMGRO_BOX)
    scopes = row_scopes(TOMGRO_BOX.layout, TOMGRO_BOX.envelope)
    course = StepCourse(
        hours=tuple(
            HourDrivers(
                temperature_c=22.0, par_above_umol_m2_s=400.0 * (6 <= hour < 18), co2_ppm=420.0
            )
            for hour in range(HOURS_A_DAY)
        )
    )
    grown = rung.planted()
    for _ in range(DAYS):
        grown = rung.live_step(grown, course)
    instances: list[AreaInstance[Any]] = [
        AreaInstance(scope_id=scope.scope_id, state=grown) for scope in scopes
    ]
    lived = [dict.fromkeys((scope.scope_id for scope in scopes), course)] * DAYS

    assert profile is HOUSE_HOURS and profile.refusal(rung.drivers) is None
    assert rung.canopy_height_m == ReducedTomgroCrop().canopy_height_m
    state = registered.state.model_validate({"instances": instances, "lived": lived})
    assert registered.state.model_validate_json(state.model_dump_json()) == state
    assert state.named == [scope.scope_id for scope in scopes] and state.plants == []
    assert registered.implausible(state, DAYS) == []
    past = grown.model_copy(update={"lai": 5.0})
    (problem,) = registered.implausible(
        state.model_copy(update={"instances": [AreaInstance(scope_id="row_1", state=past)]}), DAYS
    )
    assert problem == "row_1's leaf area index is 5, past 4"
    drawn = registered.area.drawn(instances, TOMGRO_BOX)
    assert [(entity.kind, entity.properties["scope"]) for entity in drawn] == [
        (SceneEntityKind.CANOPY, instance.scope_id) for instance in instances
    ]


# What asks a crop model for anything: the services, the routes over them
# and the ground truth; and what may name a model's rung or its plants' type
# among them: its registration.
_ASKING: Final = ("services", "api", "ground_truth.py")
_REGISTERED: Final = "services/crop_models.py"


def test_no_service_asks_which_crop_model_it_holds() -> None:
    """A service asks what a crop model declares (decision 0062), never which
    model it is: none but its registration names a model's rung or the
    simple crop's plants."""
    package = Path(greenhouse_sim.__file__).parent
    modules = [
        path
        for asking in _ASKING
        for path in sorted(
            (package / asking).rglob("*.py") if (package / asking).is_dir() else [package / asking]
        )
        if path.relative_to(package).as_posix() != _REGISTERED
    ]
    asking = [
        f"{path.relative_to(package).as_posix()}: {name}"
        for path in modules
        for name in ("OrganRung", "SimpleRung", "SimplePlant", "is_organ")
        if re.search(rf"\b{name}\b", path.read_text())
    ]
    assert len(modules) > 20
    assert asking == []
