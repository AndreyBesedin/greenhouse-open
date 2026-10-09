"""What the greenhouse's air carries, as its environment fields describe it."""

from enum import StrEnum
from typing import Final


class AirQuantity(StrEnum):
    """One thing a field says about the air at a point."""

    # Where the air moves, and how fast.
    VELOCITY = "velocity"
    TEMPERATURE = "temperature"
    # Relative humidity.
    HUMIDITY = "humidity"
    CO2 = "co2"
    # Relative to the outside air's.
    PRESSURE = "pressure"
    # The sun's and the sky's light on a level surface (P08): its
    # photosynthetically active photons, and its shortwave energy.
    PAR = "par"
    IRRADIANCE = "irradiance"


# Each quantity's unit, as its values are given.
AIR_UNITS: Final = {
    AirQuantity.VELOCITY: "m/s",
    AirQuantity.TEMPERATURE: "°C",
    AirQuantity.HUMIDITY: "%",
    AirQuantity.CO2: "ppm",
    AirQuantity.PRESSURE: "Pa",
    AirQuantity.PAR: "µmol/m²/s",
    AirQuantity.IRRADIANCE: "W/m²",
}
# The quantities with a direction: three components, along x, y and z.
VECTOR_QUANTITIES: Final = frozenset({AirQuantity.VELOCITY})
