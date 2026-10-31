"""A run's seed (P17.2, decision 0065): a scenario at a seed. A run at the
scenario's own seed is the run it always was; another seed is another run,
whose weather, sensors' noise and crop's draws differ, and which is the same
again when asked for again."""

import pytest

from greenhouse_sim.api.routes.runs import run_request
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario, with_weather
from greenhouse_sim.services.sensors import observations, run_start
from greenhouse_sim.services.simulator import Simulator

SCENARIO = "reference_greenhouse"
OWN_SEED = SCENARIO_REGISTRY[SCENARIO].random_seed
HOUR_S = 3600.0


def _values(simulator: Simulator, run: RunRequest) -> list[float]:
    return [o.value for o in observations(simulator, run, 2 * HOUR_S).observations]


def test_a_run_at_the_scenarios_own_seed_is_the_run_it_always_was(simulator: Simulator) -> None:
    plain, explicit = RunRequest(SCENARIO), RunRequest(SCENARIO, seed=OWN_SEED)
    assert explicit.weather_name(simulator.catalogue) == plain.weather_name(simulator.catalogue)
    assert air_through_a_run(simulator, explicit)[1] == air_through_a_run(simulator, plain)[1]
    assert _values(simulator, explicit) == _values(simulator, plain)


def test_another_seed_is_another_run_that_is_the_same_when_asked_again(
    simulator: Simulator,
) -> None:
    first, second = RunRequest(SCENARIO, seed=1), RunRequest(SCENARIO, seed=2)
    assert first.weather_name(simulator.catalogue) == "default#1"
    identities = {
        air_through_a_run(simulator, run)[1] for run in (RunRequest(SCENARIO), first, second)
    }
    assert len(identities) == 3
    assert air_through_a_run(simulator, first)[1] == air_through_a_run(simulator, first)[1]
    assert _values(simulator, first) == _values(simulator, RunRequest(SCENARIO, seed=1))
    assert _values(simulator, first) != _values(simulator, second)
    assert _values(simulator, first) != _values(simulator, RunRequest(SCENARIO))


def test_a_seed_reaches_the_crops_walk(simulator: Simulator) -> None:
    start = run_start(simulator.catalogue, SCENARIO)

    def walk(seed: int | None) -> list[float]:
        walked, _ = crop_records(simulator, RunRequest(SCENARIO, seed=seed), 1, start, "r")
        return [o.value for o in walked]

    assert walk(1) == walk(1)
    assert walk(1) != walk(2)
    assert walk(OWN_SEED) == walk(None)


def test_a_seed_goes_with_the_other_overrides_of_a_weather(simulator: Simulator) -> None:
    config = with_weather(scenario(simulator.catalogue, SCENARIO), "cold_spring_day@80~270#7")
    assert (config.random_seed, config.cloud_cover_pct, config.wind_from_deg) == (7, 80.0, 270.0)


@pytest.mark.parametrize("seed", ["", "x", "-1", "1.5", "٣"])
def test_a_seed_is_a_whole_number(simulator: Simulator, seed: str) -> None:
    with pytest.raises(InvalidRequest, match="whole number"):
        with_weather(scenario(simulator.catalogue, SCENARIO), f"default#{seed}")
    if seed:
        with pytest.raises(InvalidRequest, match="whole number"):
            run_request(SCENARIO, {"seed": [seed]})


def test_an_address_names_a_seed(simulator: Simulator) -> None:
    assert run_request(SCENARIO, {"seed": ["7"]}).seed == 7
    assert run_request(SCENARIO, {}).seed is None


def test_a_checkpoint_of_a_seeded_run_carries_its_seed(simulator: Simulator) -> None:
    saved = checkpoints.save_checkpoint(simulator, RunRequest(SCENARIO, seed=3), time_s=DAY_S)
    assert saved.weather == "default#3"
    kept = checkpoints.checkpoint(simulator, saved.checkpoint_id)
    assert kept.run().weather == "default#3"
    assert (
        air_through_a_run(simulator, kept.run())[1]
        == air_through_a_run(simulator, RunRequest(SCENARIO, seed=3))[1]
    )
