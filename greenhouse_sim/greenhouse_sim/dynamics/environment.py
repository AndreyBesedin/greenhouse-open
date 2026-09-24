import numpy as np

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world import GreenhouseEnvironment


def advance_environment(
    environment: GreenhouseEnvironment,
    config: ScenarioConfig,
    rng: np.random.Generator,
) -> GreenhouseEnvironment:
    """Evolve yesterday's environment into today's via a small mean-reverting drift.

    Coherent weather periods, rather than every day being an independent draw.
    """
    temp_low, temp_high = config.air_temperature_bounds
    temp_center = (temp_low + temp_high) / 2
    temp_drift = rng.normal(0.0, 0.6) + 0.1 * (temp_center - environment.air_temperature_c)
    air_temperature_c = float(
        np.clip(environment.air_temperature_c + temp_drift, temp_low, temp_high)
    )

    humidity_low, humidity_high = config.humidity_bounds
    humidity_center = (humidity_low + humidity_high) / 2
    humidity_drift = rng.normal(0.0, 1.5) + 0.1 * (humidity_center - environment.humidity_pct)
    humidity_pct = float(
        np.clip(environment.humidity_pct + humidity_drift, humidity_low, humidity_high)
    )

    return GreenhouseEnvironment(air_temperature_c=air_temperature_c, humidity_pct=humidity_pct)


def initial_environment(config: ScenarioConfig) -> GreenhouseEnvironment:
    temp_low, temp_high = config.air_temperature_bounds
    humidity_low, humidity_high = config.humidity_bounds
    return GreenhouseEnvironment(
        air_temperature_c=(temp_low + temp_high) / 2,
        humidity_pct=(humidity_low + humidity_high) / 2,
    )
