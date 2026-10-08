"""Every plant, environment and sensor model honours its contract.

The rules are stated in each domain's `contract.py`. The tests take the
implementations as parameters, so a new model joins by being added to one of
the lists below, and the lists' annotations make mypy check that it satisfies
the protocol.
"""

from datetime import UTC, datetime

import pytest
from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.observation import Observation

from greenhouse_sim.biology.contract import PlantModel
from greenhouse_sim.biology.tomato.simple.model import SimpleTomatoModel
from greenhouse_sim.biology.tomato.simple.state import SimpleTomatoState
from greenhouse_sim.environment.contract import EnvironmentModel
from greenhouse_sim.environment.simple import SimpleEnvironmentModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.sensors.contract import SensorModel
from greenhouse_sim.sensors.generation import SimpleSensorModel
from greenhouse_sim.world import GreenhouseEnvironment, GreenhouseWorld, PlantWorld
from greenhouse_sim.world_builder import advance_world, initialize_world

PLANT_MODELS: list[PlantModel[SimpleTomatoState]] = [SimpleTomatoModel()]
ENVIRONMENT_MODELS: list[EnvironmentModel] = [SimpleEnvironmentModel()]
SENSOR_MODELS: list[SensorModel] = [SimpleSensorModel()]

CONFIG = SCENARIO_REGISTRY["climate_box"]
# Deliberately unsorted, so preserving order is not the same as sorting.
PLANT_IDS = ["climate_box_plant_003", "climate_box_plant_001", "climate_box_plant_002"]
# Long enough in the climate box for trusses, fruit and ripe fruit to appear.
DAYS = 28
TIMESTAMP = datetime(2026, 1, 28, 12, 0, tzinfo=UTC)
SIMULATION_ID = "sim_contract"


def _name(model: object) -> str:
    return type(model).__name__


def _climate(model: EnvironmentModel) -> list[GreenhouseEnvironment]:
    environment = model.initial(CONFIG)
    days = []
    for day in range(1, DAYS + 1):
        environment = model.advance(environment, CONFIG, day)
        days.append(environment)
    return days


def _grow(
    model: PlantModel[SimpleTomatoState], plant_ids: list[str]
) -> tuple[list[PlantWorld], SimpleTomatoState]:
    plants, state = model.initialize(plant_ids, CONFIG)
    for environment in _climate(SimpleEnvironmentModel()):
        plants, state = model.advance(plants, state, environment, CONFIG)
    return plants, state


def _world() -> GreenhouseWorld:
    world = initialize_world(CONFIG, PLANT_IDS)
    for day in range(1, DAYS + 1):
        world = advance_world(world, CONFIG, day)
    return world


def _observe(model: SensorModel, world: GreenhouseWorld) -> list[Observation]:
    return model.observe(world, CONFIG, day=DAYS, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID)


@pytest.mark.parametrize("model", PLANT_MODELS, ids=_name)
def test_a_plant_model_keeps_each_plant_and_its_place(
    model: PlantModel[SimpleTomatoState],
) -> None:
    plants, state = model.initialize(PLANT_IDS, CONFIG)
    assert [plant.plant_id for plant in plants] == PLANT_IDS

    for environment in _climate(SimpleEnvironmentModel()):
        plants, state = model.advance(plants, state, environment, CONFIG)
        assert [plant.plant_id for plant in plants] == PLANT_IDS


@pytest.mark.parametrize("model", PLANT_MODELS, ids=_name)
def test_a_plant_model_is_deterministic(model: PlantModel[SimpleTomatoState]) -> None:
    assert _grow(model, PLANT_IDS) == _grow(model, PLANT_IDS)


@pytest.mark.parametrize("model", PLANT_MODELS, ids=_name)
def test_a_plant_model_leaves_its_arguments_unmodified(
    model: PlantModel[SimpleTomatoState],
) -> None:
    plants, state = _grow(model, PLANT_IDS)
    assert any(truss.fruits for plant in plants for truss in plant.trusses)
    plants_before = [plant.model_copy(deep=True) for plant in plants]
    state_before = state.model_copy(deep=True)

    model.advance(plants, state, _climate(SimpleEnvironmentModel())[-1], CONFIG)

    assert plants == plants_before
    assert state == state_before


@pytest.mark.parametrize("model", PLANT_MODELS, ids=_name)
def test_a_plant_model_advances_each_plant_whatever_else_is_in_the_crop(
    model: PlantModel[SimpleTomatoState],
) -> None:
    alone, _ = _grow(model, ["climate_box_plant_002"])
    crowded, _ = _grow(model, PLANT_IDS)

    assert crowded[PLANT_IDS.index("climate_box_plant_002")] == alone[0]


@pytest.mark.parametrize("model", PLANT_MODELS, ids=_name)
def test_a_plant_models_state_survives_a_json_round_trip(
    model: PlantModel[SimpleTomatoState],
) -> None:
    _, state = _grow(model, PLANT_IDS)

    assert type(state).model_validate_json(state.model_dump_json()) == state


@pytest.mark.parametrize("model", ENVIRONMENT_MODELS, ids=_name)
def test_an_environment_model_is_deterministic(model: EnvironmentModel) -> None:
    assert model.initial(CONFIG) == model.initial(CONFIG)
    assert _climate(model) == _climate(model)


@pytest.mark.parametrize("model", ENVIRONMENT_MODELS, ids=_name)
def test_an_environment_model_leaves_its_argument_unmodified(model: EnvironmentModel) -> None:
    environment = model.initial(CONFIG)
    before = environment.model_copy(deep=True)

    model.advance(environment, CONFIG, 1)

    assert environment == before


@pytest.mark.parametrize("model", SENSOR_MODELS, ids=_name)
def test_a_sensor_models_observations_pass_the_canonical_conformance_checks(
    model: SensorModel,
) -> None:
    observations = _observe(model, _world())

    assert observations
    assert check_observations(observations) == []


@pytest.mark.parametrize("model", SENSOR_MODELS, ids=_name)
def test_a_sensor_model_stamps_and_scopes_every_observation(model: SensorModel) -> None:
    world = _world()
    plant_ids = {plant.plant_id for plant in world.plants}

    for observation in _observe(model, world):
        assert observation.timestamp == TIMESTAMP
        assert observation.source.source_id == SIMULATION_ID
        assert observation.greenhouse_id == world.greenhouse_id
        assert observation.plant_id is None or observation.plant_id in plant_ids


@pytest.mark.parametrize("model", SENSOR_MODELS, ids=_name)
def test_a_sensor_model_is_deterministic_and_leaves_the_world_unmodified(
    model: SensorModel,
) -> None:
    world = _world()
    before = world.model_copy(deep=True)

    assert _observe(model, world) == _observe(model, world)
    assert world == before
