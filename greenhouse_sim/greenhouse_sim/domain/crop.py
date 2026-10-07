"""The simple crop model's stages: of its fruits, their ripeness, and its
trusses (`greenhouse_sim.biology.tomato.simple`)."""

from enum import StrEnum


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
