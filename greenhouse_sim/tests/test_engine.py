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

from greenhouse_protocol.enums import ObservationType

from greenhouse_sim.biology.tomato.simple.model import SimpleTomatoModel
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.environment.contract import EnvironmentModel
from greenhouse_sim.environment.simple import SimpleEnvironmentModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY, ScenarioConfig
from greenhouse_sim.sensors.generation import SimpleSensorModel
from greenhouse_sim.world import GreenhouseEnvironment

CONFIG = SCENARIO_REGISTRY["tomato_compartment"]
PLANT_IDS = ["tomato_compartment_plant_001", "tomato_compartment_plant_002"]
TIMESTAMP = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


def _engine() -> SimulationEngine:
    return SimulationEngine(CONFIG)


def test_advancing_a_day_observes_the_world_it_produced() -> None:
    engine = _engine()
    world = engine.initialize(PLANT_IDS, greenhouse_id="tomato_compartment")

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
        _engine().initialize(PLANT_IDS, greenhouse_id="tomato_compartment"),
        day=1,
        timestamp=TIMESTAMP,
        simulation_id="sim_1",
    )
    second = _engine().advance(
        _engine().initialize(PLANT_IDS, greenhouse_id="tomato_compartment"),
        day=1,
        timestamp=TIMESTAMP,
        simulation_id="sim_1",
    )

    assert first == second


def test_by_default_the_engine_runs_the_simple_models() -> None:
    explicit = SimulationEngine(
        CONFIG,
        environment_model=SimpleEnvironmentModel(),
        plant_model=SimpleTomatoModel(),
        sensor_model=SimpleSensorModel(),
    )
    by_default = _engine()
    worlds = [
        engine.initialize(PLANT_IDS, greenhouse_id="tomato_compartment")
        for engine in (explicit, by_default)
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
    world = engine.initialize(PLANT_IDS, greenhouse_id="tomato_compartment")

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
    assert all(
        plant.stem_length_cm > CONFIG.simple_crop.initial_stem_length_cm for plant in world.plants
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

        from greenhouse_sim.engine import SimulationEngine
        from greenhouse_sim.scenarios import SCENARIO_REGISTRY

        config = SCENARIO_REGISTRY["tomato_compartment"]
        engine = SimulationEngine(config)
        world = engine.initialize(["p1", "p2"], greenhouse_id="tomato_compartment")
        timestamp = datetime(2026, 4, 1, tzinfo=UTC)
        for day in range(1, 4):
            step = engine.advance(
                world, day=day, timestamp=timestamp, simulation_id="sim"
            )
            world = step.world
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
