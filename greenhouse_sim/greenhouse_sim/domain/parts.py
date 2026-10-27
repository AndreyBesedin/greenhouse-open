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
    # The sun's and the sky's light, through the glazing, onto the house and
    # its crop (P08, `greenhouse_sim.solar`).
    SUNLIGHT = "sunlight"
    # The sensors' readings of the run (P06, `greenhouse_sim.sensors.air`).
    SENSORS = "sensors"
