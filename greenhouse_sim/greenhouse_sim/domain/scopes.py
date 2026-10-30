"""The kinds of a crop's scopes and of the areas its quantities are per
(decision 0062, `greenhouse_sim.world.scopes`)."""

from enum import StrEnum


class ScopeKind(StrEnum):
    """What a crop instance grows on: one row of the crop rows. A bed, a
    growing zone, a compartment and the house are as possible (decision
    0062), and none is a scope yet."""

    ROW = "row"


class AreaBasis(StrEnum):
    """The area a crop model's quantities are per m² of: a scope's floor,
    its share of the house's, or its cultivated area, the ground its
    planting positions take."""

    FLOOR = "floor"
    CULTIVATED = "cultivated"
