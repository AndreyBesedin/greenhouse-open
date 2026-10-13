"""A run's processes (P09.2), in the order they take their turns at a
moment: commands, then the air, then the plants, then the sensors, then the
cameras, so that an observation at a moment sees what changed at it."""

from enum import StrEnum


class Process(StrEnum):
    """A run's processes, in the order they take their turns at a moment."""

    COMMANDS = "commands"
    AIR = "air"
    PLANTS = "plants"
    SENSORS = "sensors"
    CAMERAS = "cameras"
