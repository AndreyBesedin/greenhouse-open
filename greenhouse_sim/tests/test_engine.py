"""The simulator's API, exercised with nothing else around it.

The simulator runs without a database, a server or a UI. These tests are
deliberately narrow and use no fixtures, so the day that stops being true
they fail rather than quietly pass through a fixture.
"""

import pathlib
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta

from greenhouse_protocol.action import HarvestPlantAction, LowerPlantAction, WaterPlantAction
from greenhouse_protocol.enums import ActionExecutorType, EventType, ObservationType

from greenhouse_sim.biology.tomato.simple.model import SimpleTomatoModel
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.environment.contract import EnvironmentModel
from greenhouse_sim.environment.simple import SimpleEnvironmentModel
from greenhouse_sim.executor import SimulatedOperatorExecutor, executor_for
from greenhouse_sim.scenarios import SCENARIO_REGISTRY, ScenarioConfig
from greenhouse_sim.sensors.generation import SimpleSensorModel
from greenhouse_sim.world import GreenhouseEnvironment

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_IDS = ["gh_001_plant_001", "gh_001_plant_002"]
TIMESTAMP = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


def _engine() -> SimulationEngine:
    return SimulationEngine(CONFIG)


def test_advancing_a_day_observes_the_world_it_produced() -> None:
    engine = _engine()
    world = engine.initialize(PLANT_IDS, greenhouse_id="gh_001")

    step = engine.advance(world, day=1, timestamp=TIMESTAMP, simulation_id="sim_1")

    assert step.day == 1
    assert step.timestamp == TIMESTAMP
    assert step.world.simulated_day == 1
    assert step.observations
    assert all(o.timestamp == TIMESTAMP for o in step.observations)
    assert all(o.source.source_id == "sim_1" for o in step.observations)
    # The caller is given the advanced world, not the one it passed in.
    assert world.simulated_day == 0


def test_the_same_day_advances_the_same_way_twice() -> None:
    first = _engine().advance(
        _engine().initialize(PLANT_IDS, greenhouse_id="gh_001"),
        day=1,
        timestamp=TIMESTAMP,
        simulation_id="sim_1",
    )
    second = _engine().advance(
        _engine().initialize(PLANT_IDS, greenhouse_id="gh_001"),
        day=1,
        timestamp=TIMESTAMP,
        simulation_id="sim_1",
    )

    assert first == second


def test_an_accepted_action_changes_the_world_and_reports_an_event() -> None:
    engine = _engine()
    world = engine.initialize(PLANT_IDS, greenhouse_id="gh_001")
    step = engine.advance(world, day=1, timestamp=TIMESTAMP, simulation_id="sim_1")
    before = step.world.plant(PLANT_IDS[0]).water_reservoir_ml

    execution = engine.apply_actions(
        step.world,
        [WaterPlantAction(plant_id=PLANT_IDS[0], amount_ml=500.0)],
        day=1,
        timestamp=TIMESTAMP,
    )

    assert [result.accepted for result in execution.results] == [True]
    assert [event.event_type for event in execution.events] == [EventType.WATERING]
    assert execution.world.plant(PLANT_IDS[0]).water_reservoir_ml > before


def test_a_rejected_action_keeps_its_place_and_produces_no_event() -> None:
    """A request is not evidence that anything happened."""
    engine = _engine()
    step = engine.advance(
        engine.initialize(PLANT_IDS, greenhouse_id="gh_001"),
        day=1,
        timestamp=TIMESTAMP,
        simulation_id="sim_1",
    )

    execution = engine.apply_actions(
        step.world,
        [
            WaterPlantAction(plant_id="no_such_plant", amount_ml=500.0),
            WaterPlantAction(plant_id=PLANT_IDS[0], amount_ml=999_999.0),
            HarvestPlantAction(plant_id=PLANT_IDS[0]),
        ],
        day=1,
        timestamp=TIMESTAMP,
    )

    assert [result.accepted for result in execution.results] == [False, False, True]
    assert execution.results[0].reason is not None
    assert len(execution.events) == 1


def test_actions_are_applied_in_order_against_one_world() -> None:
    engine = _engine()
    step = engine.advance(
        engine.initialize(PLANT_IDS, greenhouse_id="gh_001"),
        day=1,
        timestamp=TIMESTAMP,
        simulation_id="sim_1",
    )
    plant = step.world.plant(PLANT_IDS[0])
    # Lowering the full visible height is admissible; a second identical
    # request is not, because the first one already consumed it.
    amount = plant.stem_length_cm - plant.lowered_length_cm

    execution = engine.apply_actions(
        step.world,
        [
            LowerPlantAction(plant_id=PLANT_IDS[0], amount_cm=amount),
            LowerPlantAction(plant_id=PLANT_IDS[0], amount_cm=amount),
        ],
        day=1,
        timestamp=TIMESTAMP,
    )

    assert [result.accepted for result in execution.results] == [True, False]


def test_by_default_the_engine_runs_the_simple_models() -> None:
    explicit = SimulationEngine(
        CONFIG,
        environment_model=SimpleEnvironmentModel(),
        plant_model=SimpleTomatoModel(),
        sensor_model=SimpleSensorModel(),
    )
    by_default = _engine()
    worlds = [
        engine.initialize(PLANT_IDS, greenhouse_id="gh_001") for engine in (explicit, by_default)
    ]

    for day in range(1, 8):
        timestamp = TIMESTAMP + timedelta(days=day)
        steps = [
            engine.advance(world, day=day, timestamp=timestamp, simulation_id="sim_1")
            for engine, world in zip((explicit, by_default), worlds, strict=True)
        ]
        assert steps[0] == steps[1]
        worlds = [step.world for step in steps]


class _ConstantClimate:
    """The simplest other environment model: the same weather every day."""

    CLIMATE = GreenhouseEnvironment(air_temperature_c=30.0, humidity_pct=50.0)

    def initial(self, config: ScenarioConfig) -> GreenhouseEnvironment:
        return self.CLIMATE

    def advance(
        self, environment: GreenhouseEnvironment, config: ScenarioConfig, day: int
    ) -> GreenhouseEnvironment:
        return environment


def test_the_engine_runs_the_environment_model_it_is_given() -> None:
    """A model plugged in through its contract drives the world and what the
    sensors report, with no change to the engine."""
    climate: EnvironmentModel = _ConstantClimate()
    engine = SimulationEngine(CONFIG, environment_model=climate)
    world = engine.initialize(PLANT_IDS, greenhouse_id="gh_001")

    for day in range(1, 8):
        step = engine.advance(
            world, day=day, timestamp=TIMESTAMP + timedelta(days=day), simulation_id="sim_1"
        )
        world = step.world
        readings = [
            o.value
            for o in step.observations
            if o.observation_type == ObservationType.AIR_TEMPERATURE_C
        ]
        assert world.environment == _ConstantClimate.CLIMATE
        assert readings and all(abs(reading - 30.0) < 2.0 for reading in readings)
    assert all(plant.stem_length_cm > CONFIG.initial_stem_length_cm for plant in world.plants)


def test_executor_for_resolves_the_simulated_operator() -> None:
    assert isinstance(
        executor_for(ActionExecutorType.SIMULATED_OPERATOR), SimulatedOperatorExecutor
    )


def test_a_whole_run_loads_no_database_web_framework_or_api() -> None:
    """The simulator runs standalone, checked at runtime.

    The dependency test proves no simulator source file imports anything
    undeclared. This proves the consequence a standalone user experiences:
    driving the engine never loads a database layer, a web framework, an HTTP
    server or the simulator's own local API. Run in a subprocess so modules
    imported by other tests do not count.
    """
    program = textwrap.dedent(
        """
        import sys
        from datetime import UTC, datetime

        from greenhouse_protocol.action import WaterPlantAction
        from greenhouse_sim.engine import SimulationEngine
        from greenhouse_sim.scenarios import SCENARIO_REGISTRY

        config = SCENARIO_REGISTRY["gh_001"]
        engine = SimulationEngine(config)
        world = engine.initialize(["p1", "p2"], greenhouse_id="gh_001")
        timestamp = datetime(2026, 4, 1, tzinfo=UTC)
        for day in range(1, 4):
            step = engine.advance(
                world, day=day, timestamp=timestamp, simulation_id="sim"
            )
            world = engine.apply_actions(
                step.world,
                [WaterPlantAction(plant_id="p1", amount_ml=100.0)],
                day=day,
                timestamp=timestamp,
            ).world
        assert step.observations

        leaked = sorted(
            name
            for name in sys.modules
            if name.split(".")[0] in {"sqlalchemy", "fastapi", "starlette"}
            or name == "http.server"
            or name.startswith("greenhouse_sim.api")
        )
        print(",".join(leaked))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=pathlib.Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"simulator loaded: {result.stdout!r}"
