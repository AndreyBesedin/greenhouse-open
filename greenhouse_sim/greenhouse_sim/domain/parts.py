"""The parts of a run a manifest chooses a model for (decision 0054,
`greenhouse_sim.scenarios.registry`)."""

from enum import StrEnum


class Part(StrEnum):
    """What a run needs worked out, of the parts a manifest chooses a model
    for."""

    WEATHER = "weather"
    AIR_FIELD = "air_field"
    CROP = "crop"
    CROP_WALK = "crop_walk"
