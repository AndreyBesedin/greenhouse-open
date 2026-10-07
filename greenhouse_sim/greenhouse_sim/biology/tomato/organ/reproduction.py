"""Trusses, flowers and fruit set: how a plant's reproductive organs develop.

A tomato's first truss appears on a set phytomer of its main stem, and
another on every few phytomers above it; each appears with its phytomer. A
truss bears a number of flowers drawn when it appears, which appear one
after another from its base. A flower is a bud until its anthesis, open
after, and some time later it either sets fruit or aborts, by its own draw:
flowers near the truss's base set more often than those at its tip. A fruit
takes its flower's place, appearing when the flower set, and grows and
ripens as `fruit` says; while young it may still abort, by the fruit's own
draw.

Every event happens at a set thermal age, and every chance is drawn from the
organ's own generator once, when its moment comes, so a plant grown in one
step or day by day sets the same fruit.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

from greenhouse_sim.biology.plant.organs import Flower, Fruit
from greenhouse_sim.biology.plant.seeds import organ_rng
from greenhouse_sim.biology.tomato.organ.fruit import FruitParams, grown_fruit, set_fruit
from greenhouse_sim.biology.tomato.organ.topology import Plant, Truss, flower_id, fruit_id, truss_id
from greenhouse_sim.domain.organs import FlowerStage, FruitStage

type Probability = Annotated[float, Field(ge=0, le=1)]


class TrussParams(BaseModel):
    """When trusses appear and how their flowers develop, with a greenhouse
    tomato's typical values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The first truss appears on this phytomer, and another every this many
    # phytomers above it.
    first_truss_rank: PositiveInt = 8
    truss_interval: PositiveInt = 3
    # A truss bears from this many flowers to this many, drawn evenly.
    min_flowers: PositiveInt = 4
    max_flowers: PositiveInt = 8
    # Thermal time between one flower's appearance and the next's, in °Cd.
    flower_interval_cd: PositiveFloat = 8.0
    # A flower opens this long after it appears, and sets or aborts this long
    # after it opens, in °Cd.
    anthesis_cd: PositiveFloat = 180.0
    set_decision_cd: PositiveFloat = 60.0
    # The chance that a truss's first flower sets fruit, and how much less
    # likely each flower further along the truss is.
    basal_set_probability: Probability = 0.9
    distal_set_decline: Probability = 0.05
    # The chance that a young fruit aborts, decided this long after it set.
    fruit_abortion_probability: Probability = 0.05
    fruit_abortion_cd: PositiveFloat = 100.0
    # How fruits grow and ripen.
    fruits: FruitParams = FruitParams()

    @model_validator(mode="after")
    def _flowers_in_order(self) -> Self:
        if self.min_flowers > self.max_flowers:
            raise ValueError("min_flowers is more than max_flowers")
        return self

    def set_probability(self, rank: int) -> float:
        """The chance that the flower in this place on its truss sets fruit."""
        return max(0.0, self.basal_set_probability - self.distal_set_decline * (rank - 1))


def bears_truss(rank: int, params: TrussParams) -> bool:
    """Whether a phytomer of this rank appears with a truss."""
    above_first = rank - params.first_truss_rank
    return above_first >= 0 and above_first % params.truss_interval == 0


def new_truss(plant: Plant, number: int, born_tt: float, params: TrussParams) -> Truss:
    """The plant's truss of this number as it appears, its flower count drawn
    from its own generator and no flower yet."""
    truss = truss_id(plant.plant_id, number)
    rng = organ_rng(plant.seed, plant.plant_id, truss, "flowers")
    count = int(rng.integers(params.min_flowers, params.max_flowers + 1))
    return Truss(truss_id=truss, number=number, born_tt=born_tt, final_flower_count=count)


def _decided(plant: Plant, organ_id: str, process: str, chance: float) -> bool:
    """Whether an organ's chance, drawn from its own generator, came up."""
    return float(organ_rng(plant.seed, plant.plant_id, organ_id, process).uniform()) < chance


def _fruit_at(
    plant: Plant,
    fruit: Fruit,
    previous_tt: float,
    thermal_time: float,
    params: TrussParams,
    growth: float,
) -> Fruit:
    """The fruit at the plant's thermal time: grown and ripened while it is on
    the plant. One whose moment to abort comes on the way aborts, or not, by
    its draw, and if it does, stays as it was then."""
    if fruit.stage != FruitStage.ATTACHED:
        return fruit
    decided_at = fruit.born_tt + params.fruit_abortion_cd
    if previous_tt < decided_at <= thermal_time and _decided(
        plant, fruit.fruit_id, "abortion", params.fruit_abortion_probability
    ):
        aborted = grown_fruit(fruit, previous_tt, decided_at, params.fruits, growth)
        return aborted.model_copy(update={"stage": FruitStage.ABORTED})
    return grown_fruit(fruit, previous_tt, thermal_time, params.fruits, growth)


def _flower_at(
    plant: Plant,
    truss: Truss,
    flower: Flower,
    previous_tt: float,
    thermal_time: float,
    params: TrussParams,
    growth: float,
) -> Flower:
    """The flower at the plant's thermal time: a bud, open, or once its
    moment has come, set as its fruit or aborted."""
    if flower.stage == FlowerStage.ABORTED:
        return flower
    if flower.stage == FlowerStage.SET and flower.fruit is not None:
        fruit = _fruit_at(plant, flower.fruit, previous_tt, thermal_time, params, growth)
        return flower.model_copy(update={"fruit": fruit})
    opens_at = flower.born_tt + params.anthesis_cd
    decided_at = opens_at + params.set_decision_cd
    if thermal_time < opens_at:
        return flower.model_copy(update={"stage": FlowerStage.BUD})
    if thermal_time < decided_at:
        return flower.model_copy(update={"stage": FlowerStage.OPEN})
    if not _decided(plant, flower.flower_id, "fruit_set", params.set_probability(flower.rank)):
        return flower.model_copy(update={"stage": FlowerStage.ABORTED})
    fruit = set_fruit(
        plant,
        fruit_id(plant.plant_id, truss.number, flower.rank),
        flower.rank,
        decided_at,
        params.fruits,
    )
    # A fruit set within this step may already have reached its own moment.
    fruit = _fruit_at(plant, fruit, decided_at, thermal_time, params, growth)
    return flower.model_copy(update={"stage": FlowerStage.SET, "fruit": fruit})


def grown_truss(
    plant: Plant,
    truss: Truss,
    previous_tt: float,
    thermal_time: float,
    params: TrussParams,
    growth: float = 1.0,
) -> Truss:
    """The truss as the plant's thermal time moves on from `previous_tt`: its
    flowers appeared up to its count, each when its time is up, and each
    developed, its fruits making `growth` of their potential growth."""
    flowers = list(truss.flowers)
    while len(flowers) < truss.final_flower_count:
        rank = len(flowers) + 1
        born = truss.born_tt + (rank - 1) * params.flower_interval_cd
        if born > thermal_time:
            break
        flowers.append(
            Flower(flower_id=flower_id(plant.plant_id, truss.number, rank), rank=rank, born_tt=born)
        )
    grown = tuple(
        _flower_at(plant, truss, flower, previous_tt, thermal_time, params, growth)
        for flower in flowers
    )
    return truss.model_copy(update={"flowers": grown})
