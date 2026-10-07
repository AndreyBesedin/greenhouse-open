"""The organs fruiting crops share, and how a plant differs from its crop.

A plant's main stem is made of phytomers, stacked from the bottom up and
numbered from 1, its rank: each a node with the internode below it and a
leaf. Flowers become fruits when they set. Every organ records when it
appeared, as its plant's accumulated thermal time then, in degree-days (°Cd).
What bears the flowers, and how the plant holds them all together, is each
crop's own: the tomato's is `greenhouse_sim.biology.tomato.organ.topology`.

Identifiers say where an organ sits:

    p01                 a plant
    p01_stem            its main stem
    p01_n05             its fifth phytomer (node)
    p01_n05_internode   that phytomer's internode, below its node
    p01_n05_leaf        that phytomer's leaf
"""

import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, PositiveInt

from greenhouse_sim.domain.organs import FlowerStage, FruitStage, LeafStage


def stem_id(plant_id: str) -> str:
    return f"{plant_id}_stem"


def phytomer_id(plant_id: str, rank: int) -> str:
    return f"{plant_id}_n{rank:02d}"


def internode_id(plant_id: str, rank: int) -> str:
    return f"{phytomer_id(plant_id, rank)}_internode"


def leaf_id(plant_id: str, rank: int) -> str:
    return f"{phytomer_id(plant_id, rank)}_leaf"


class Organ(BaseModel):
    """What every organ has: when it appeared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The plant's accumulated thermal time when the organ appeared, in °Cd.
    born_tt: NonNegativeFloat


class Internode(Organ):
    internode_id: str
    length_cm: NonNegativeFloat
    diameter_mm: NonNegativeFloat
    # The sizes it grows towards, fixed when it appears.
    final_length_cm: NonNegativeFloat
    final_diameter_mm: NonNegativeFloat


class Leaf(Organ):
    leaf_id: str
    length_cm: NonNegativeFloat
    # The length it grows towards, fixed when it appears.
    final_length_cm: NonNegativeFloat
    stage: LeafStage = LeafStage.EXPANDING


class Fruit(Organ):
    fruit_id: str
    diameter_mm: NonNegativeFloat
    # The diameter it grows towards, fixed when it sets.
    final_diameter_mm: NonNegativeFloat
    # Its fresh mass, in grams.
    mass_g: NonNegativeFloat
    # The plant's thermal time when it starts to ripen, fixed when it sets.
    breaker_tt: NonNegativeFloat
    # How far it has ripened, from 0, green, to 1, red.
    ripeness: Annotated[float, Field(ge=0, le=1)] = 0.0
    stage: FruitStage = FruitStage.ATTACHED


class Flower(Organ):
    flower_id: str
    # Its place on what bears it, such as a tomato's truss, from its base.
    rank: PositiveInt
    stage: FlowerStage = FlowerStage.BUD
    fruit: Fruit | None = None


class PlantTraits(BaseModel):
    """How one plant differs from its crop's typical plant: a factor on each
    of the crop's values (1 for a typical plant), its turn about its stem,
    and the latent vigour its factors share."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # In standard deviations from the crop's mean; 0 for a typical plant.
    vigour: float = 0.0
    phyllochron_scale: PositiveFloat = 1.0
    internode_length_scale: PositiveFloat = 1.0
    stem_diameter_scale: PositiveFloat = 1.0
    leaf_length_scale: PositiveFloat = 1.0
    leaf_insertion_scale: PositiveFloat = 1.0
    leaf_droop_scale: PositiveFloat = 1.0
    # Where its first leaf points about its stem, from +x.
    rotation_rad: Annotated[float, Field(ge=0, lt=2 * math.pi)] = 0.0
