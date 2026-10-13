"""The crop's models, and the simple crop model's stages: of its fruits,
their ripeness, and its trusses (`greenhouse_sim.biology.tomato.simple`)."""

from enum import StrEnum


class CropModel(StrEnum):
    """How a scenario's run grows its crop: by the simple daily model,
    through the engine, or organ by organ (`greenhouse_sim.core.crop`)."""

    SIMPLE = "simple"
    ORGAN = "organ"


class FruitStatus(StrEnum):
    GROWING = "GROWING"
    RIPE = "RIPE"
    HARVESTED = "HARVESTED"


class RipenessStage(StrEnum):
    FRUIT_SET = "FRUIT_SET"
    IMMATURE_GREEN = "IMMATURE_GREEN"
    MATURE_GREEN = "MATURE_GREEN"
    TURNING = "TURNING"
    RIPE = "RIPE"
    OVERRIPE = "OVERRIPE"


class TrussStage(StrEnum):
    INITIATED = "INITIATED"
    FRUITING = "FRUITING"
    HARVESTABLE = "HARVESTABLE"
    INACTIVE = "INACTIVE"
