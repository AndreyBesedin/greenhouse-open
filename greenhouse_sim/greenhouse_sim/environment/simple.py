"""The simple environment model: one greenhouse-wide climate, day by day.

Air temperature and humidity are single values for the whole greenhouse.
Each day they drift randomly and are pulled back towards the middle of the
scenario's bounds, so warm or humid spells last a few days rather than every
day being an independent draw. There is no light, CO2, weather, equipment or
spatial variation. Like the simple tomato model, it is kept as the fast,
deterministic reference that richer environment models are compared against.
"""

from typing import Final

import numpy as np

from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseEnvironment

# Each day, temperature and humidity change by a random amount with this
# standard deviation, and are pulled back towards the middle of the
# scenario's bounds by this share of their distance from it.
TEMPERATURE_DRIFT_SD_C: Final = 0.6
HUMIDITY_DRIFT_SD_PCT: Final = 1.5
PULL_TO_MIDDLE_PER_DAY: Final = 0.1


def advance_environment(
    environment: GreenhouseEnvironment, config: ScenarioConfig, day: int
) -> GreenhouseEnvironment:
    """Evolve yesterday's environment into today's via a small mean-reverting drift.

    The day's randomness is drawn from the scenario seed and the day alone,
    so the climate does not depend on what else the simulator draws.
    """
    rng = seeded_rng(config.random_seed, day, "environment")
    temp_low, temp_high = config.air_temperature_bounds
    temp_center = (temp_low + temp_high) / 2
    temp_drift = rng.normal(0.0, TEMPERATURE_DRIFT_SD_C) + PULL_TO_MIDDLE_PER_DAY * (
        temp_center - environment.air_temperature_c
    )
    air_temperature_c = float(
        np.clip(environment.air_temperature_c + temp_drift, temp_low, temp_high)
    )

    humidity_low, humidity_high = config.humidity_bounds
    humidity_center = (humidity_low + humidity_high) / 2
    humidity_drift = rng.normal(0.0, HUMIDITY_DRIFT_SD_PCT) + PULL_TO_MIDDLE_PER_DAY * (
        humidity_center - environment.humidity_pct
    )
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
