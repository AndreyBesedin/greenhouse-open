"""A plant's organs, organ by organ: their kinds, their stages, and how a
stage may change from one moment to a later one
(`greenhouse_sim.biology.tomato.organ`)."""

from enum import StrEnum


class OrganKind(StrEnum):
    PLANT = "plant"
    AXIS = "axis"
    PHYTOMER = "phytomer"
    INTERNODE = "internode"
    LEAF = "leaf"
    TRUSS = "truss"
    FLOWER = "flower"
    FRUIT = "fruit"


class LeafStage(StrEnum):
    """Where a leaf is in its life."""

    EXPANDING = "expanding"
    MATURE = "mature"
    # Pruned off the plant; it keeps its place, so the history stays whole.
    REMOVED = "removed"


class FlowerStage(StrEnum):
    BUD = "bud"
    OPEN = "open"
    # Set fruit: the flower is now its fruit.
    SET = "set"
    # Dropped without setting fruit.
    ABORTED = "aborted"


class FruitStage(StrEnum):
    """Where a fruit is in its life, from set to picked."""

    # On the plant, growing and ripening.
    ATTACHED = "attached"
    # Dropped while young; it keeps its place, as a removed leaf does.
    ABORTED = "aborted"
    HARVESTED = "harvested"


# How each kind of organ's stage may change from one moment to a later one;
# a stage may always stay as it is.
LEAF_CHANGES: dict[LeafStage, frozenset[LeafStage]] = {
    LeafStage.EXPANDING: frozenset({LeafStage.MATURE, LeafStage.REMOVED}),
    LeafStage.MATURE: frozenset({LeafStage.REMOVED}),
    LeafStage.REMOVED: frozenset(),
}
FLOWER_CHANGES: dict[FlowerStage, frozenset[FlowerStage]] = {
    FlowerStage.BUD: frozenset({FlowerStage.OPEN, FlowerStage.SET, FlowerStage.ABORTED}),
    FlowerStage.OPEN: frozenset({FlowerStage.SET, FlowerStage.ABORTED}),
    FlowerStage.SET: frozenset(),
    FlowerStage.ABORTED: frozenset(),
}
FRUIT_CHANGES: dict[FruitStage, frozenset[FruitStage]] = {
    FruitStage.ATTACHED: frozenset({FruitStage.ABORTED, FruitStage.HARVESTED}),
    FruitStage.ABORTED: frozenset(),
    FruitStage.HARVESTED: frozenset(),
}
