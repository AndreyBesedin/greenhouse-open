"""The greenhouse's climate equipment, as more than one package names it."""

from enum import StrEnum


class ActuatorKind(StrEnum):
    """What a piece of climate equipment is, and so what it does to the air."""

    # Blows the air along its axis.
    FAN = "fan"
    # Warms the air around it.
    HEATER = "heater"
    # Takes water out of the air around it, and warms it a little.
    DEHUMIDIFIER = "dehumidifier"
