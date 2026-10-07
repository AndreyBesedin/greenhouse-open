"""A tomato plant's structure: its organs, how they are attached, and their
identities.

A plant has one main stem, its axis, made of phytomers stacked from the
bottom up and numbered from 1, the rank. Each phytomer is a node with the
internode below it and a leaf; some also carry a truss, numbered from 1 in
the order trusses appear. A truss carries flowers, numbered from 1 from its
base; a flower that sets becomes a fruit, which keeps its flower's place.

Identifiers say where an organ sits, so they never depend on anything else:

    p01                 a plant
    p01_stem            its main stem
    p01_n05             its fifth phytomer (node)
    p01_n05_internode   that phytomer's internode, below its node
    p01_n05_leaf        that phytomer's leaf
    p01_t02             its second truss
    p01_t02_fl04        that truss's fourth flower
    p01_t02_fr04        the fruit that flower set

Every organ records when it appeared, as the plant's accumulated thermal
time then (degree-days, °Cd); its thermal age is how much the plant has
accumulated since. A plant also records the seed its draws come from and its
traits: how it differs from its crop's typical plant. `topology_problems`
lists whatever breaks the structure's rules, so tests, and later the model
itself, can hold every plant to them.
"""

import math
from collections import Counter
from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
)


# The organs' kinds and stages, and the structure below, are partly generic
# to fruiting crops and partly the tomato's. Where they go once P03 is done,
# shared domain descriptors and a generic plant with tomato as one kind, is
# planned in docs/roadmap/p03-cleanup.md.
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


# What an organ never loses from one moment to a later one.
NEVER_DECREASE: tuple[str, ...] = ("length_cm", "diameter_mm", "mass_g", "ripeness")

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


def stem_id(plant_id: str) -> str:
    return f"{plant_id}_stem"


def phytomer_id(plant_id: str, rank: int) -> str:
    return f"{plant_id}_n{rank:02d}"


def internode_id(plant_id: str, rank: int) -> str:
    return f"{phytomer_id(plant_id, rank)}_internode"


def leaf_id(plant_id: str, rank: int) -> str:
    return f"{phytomer_id(plant_id, rank)}_leaf"


def truss_id(plant_id: str, number: int) -> str:
    return f"{plant_id}_t{number:02d}"


def flower_id(plant_id: str, truss: int, rank: int) -> str:
    return f"{truss_id(plant_id, truss)}_fl{rank:02d}"


def fruit_id(plant_id: str, truss: int, rank: int) -> str:
    return f"{truss_id(plant_id, truss)}_fr{rank:02d}"


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
    # Its place on the truss, from the truss's base.
    rank: PositiveInt
    stage: FlowerStage = FlowerStage.BUD
    fruit: Fruit | None = None


class Truss(Organ):
    truss_id: str
    # Its place among the plant's trusses, in the order they appeared.
    number: PositiveInt
    # How many flowers it bears in all, fixed when it appears; they appear
    # one after another from its base.
    final_flower_count: PositiveInt
    flowers: tuple[Flower, ...] = ()


class Phytomer(Organ):
    phytomer_id: str
    rank: PositiveInt
    internode: Internode
    leaf: Leaf
    truss: Truss | None = None


class Axis(Organ):
    axis_id: str
    phytomers: tuple[Phytomer, ...] = ()


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


class RemoveLeaf(BaseModel):
    """Prune a leaf off the plant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["remove_leaf"] = "remove_leaf"
    leaf_id: str


class HarvestFruit(BaseModel):
    """Pick one fruit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["harvest_fruit"] = "harvest_fruit"
    fruit_id: str


class HarvestTruss(BaseModel):
    """Cut a truss: pick its fruits, and drop the flowers it still bears."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["harvest_truss"] = "harvest_truss"
    truss_id: str


class LowerStem(BaseModel):
    """Lower the stem, laying its lowest standing internodes down along the
    row; they must be bare, their leaves removed and their trusses cut."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["lower_stem"] = "lower_stem"
    internodes: PositiveInt = 1


type PlantAction = Annotated[
    RemoveLeaf | HarvestFruit | HarvestTruss | LowerStem, Field(discriminator="kind")
]


class PlantEvent(BaseModel):
    """An action done to a plant, or asked of it and refused."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The plant's thermal time when it was done.
    thermal_time: NonNegativeFloat
    action: PlantAction
    applied: bool
    # What it did, or why it was refused, in words.
    note: str
    # The organs it changed.
    organs: tuple[str, ...] = ()
    # The fresh mass of the fruit it picked, in grams.
    harvested_g: NonNegativeFloat = 0.0


class Plant(Organ):
    """One plant, organ by organ, and the thermal time it has accumulated."""

    plant_id: str
    thermal_time: NonNegativeFloat
    stem: Axis
    # The simulation's seed, which the plant's and its organs' draws come from.
    seed: NonNegativeInt = 0
    traits: PlantTraits = PlantTraits()
    # How many of its lowest internodes have been laid down along the row.
    laid_internodes: NonNegativeInt = 0
    # Everything done to it, or asked of it, in order.
    history: tuple[PlantEvent, ...] = ()

    def thermal_age(self, organ: Organ) -> float:
        """How long an organ has developed, in °Cd."""
        return self.thermal_time - organ.born_tt

    def organs(self) -> Iterator[tuple[OrganKind, str, str | None, Organ]]:
        """Every organ with its kind, identifier and its parent's identifier,
        from the plant down, in the order they sit."""
        yield OrganKind.PLANT, self.plant_id, None, self
        yield OrganKind.AXIS, self.stem.axis_id, self.plant_id, self.stem
        for phytomer in self.stem.phytomers:
            yield OrganKind.PHYTOMER, phytomer.phytomer_id, self.stem.axis_id, phytomer
            yield (
                OrganKind.INTERNODE,
                phytomer.internode.internode_id,
                phytomer.phytomer_id,
                phytomer.internode,
            )
            yield OrganKind.LEAF, phytomer.leaf.leaf_id, phytomer.phytomer_id, phytomer.leaf
            if phytomer.truss is None:
                continue
            truss = phytomer.truss
            yield OrganKind.TRUSS, truss.truss_id, phytomer.phytomer_id, truss
            for flower in truss.flowers:
                yield OrganKind.FLOWER, flower.flower_id, truss.truss_id, flower
                if flower.fruit is not None:
                    yield OrganKind.FRUIT, flower.fruit.fruit_id, flower.flower_id, flower.fruit


def bears_anything(truss: Truss) -> bool:
    """Whether a truss still bears a flower or a fruit on the plant."""
    return any(
        flower.stage in {FlowerStage.BUD, FlowerStage.OPEN}
        or (flower.fruit is not None and flower.fruit.stage == FruitStage.ATTACHED)
        for flower in truss.flowers
    )


def topology_problems(plant: Plant) -> list[str]:
    """Everything that breaks the structure's rules, or nothing."""
    problems: list[str] = []
    pid = plant.plant_id
    counts = Counter(organ_id for _, organ_id, _, _ in plant.organs())
    repeated = sorted(organ_id for organ_id, count in counts.items() if count > 1)
    if repeated:
        problems.append(f"identifiers used twice: {', '.join(repeated)}")
    if plant.stem.axis_id != stem_id(pid):
        problems.append(f"the stem is {plant.stem.axis_id}, not {stem_id(pid)}")
    for kind, organ_id, _, organ in plant.organs():
        if organ.born_tt > plant.thermal_time:
            problems.append(f"{organ_id} appeared after the plant's thermal time")
        if kind == OrganKind.FLOWER and isinstance(organ, Flower):
            if (organ.fruit is not None) != (organ.stage == FlowerStage.SET):
                problems.append(f"{organ_id} has a fruit if and only if it set")
    trusses = 0
    previous_born = 0.0
    for expected_rank, phytomer in enumerate(plant.stem.phytomers, start=1):
        rank = phytomer.rank
        if rank != expected_rank:
            problems.append(f"phytomer {phytomer.phytomer_id} has rank {rank}, not {expected_rank}")
        if phytomer.born_tt < previous_born:
            problems.append(f"{phytomer.phytomer_id} appeared before the phytomer below it")
        previous_born = phytomer.born_tt
        expected = {
            phytomer.phytomer_id: phytomer_id(pid, rank),
            phytomer.internode.internode_id: internode_id(pid, rank),
            phytomer.leaf.leaf_id: leaf_id(pid, rank),
        }
        problems += [f"{found} should be {due}" for found, due in expected.items() if found != due]
        for child in (phytomer.internode, phytomer.leaf, phytomer.truss):
            if child is not None and child.born_tt < phytomer.born_tt:
                problems.append(f"{phytomer.phytomer_id} has an organ older than itself")
        internode, leaf = phytomer.internode, phytomer.leaf
        if internode.length_cm > internode.final_length_cm:
            problems.append(f"{internode.internode_id} is longer than it grows")
        if internode.diameter_mm > internode.final_diameter_mm:
            problems.append(f"{internode.internode_id} is thicker than it grows")
        if leaf.length_cm > leaf.final_length_cm:
            problems.append(f"{leaf.leaf_id} is longer than it grows")
        if phytomer.truss is None:
            continue
        trusses += 1
        truss = phytomer.truss
        if (truss.number, truss.truss_id) != (trusses, truss_id(pid, trusses)):
            problems.append(f"{truss.truss_id} is truss {trusses}, numbered from the bottom")
        if len(truss.flowers) > truss.final_flower_count:
            problems.append(f"{truss.truss_id} has more flowers than it bears")
        for expected_flower, flower in enumerate(truss.flowers, start=1):
            due = flower_id(pid, truss.number, expected_flower)
            if (flower.rank, flower.flower_id) != (expected_flower, due):
                problems.append(f"{flower.flower_id} should be {due}")
            if flower.born_tt < truss.born_tt:
                problems.append(f"{flower.flower_id} is older than its truss")
            fruit = flower.fruit
            if fruit is not None and fruit.fruit_id != fruit_id(pid, truss.number, flower.rank):
                problems.append(f"{fruit.fruit_id} should take its flower's place")
            if fruit is not None and fruit.born_tt < flower.born_tt:
                problems.append(f"{fruit.fruit_id} is older than its flower")
            if fruit is not None and fruit.diameter_mm > fruit.final_diameter_mm:
                problems.append(f"{fruit.fruit_id} is larger than it grows")
            if fruit is not None and fruit.breaker_tt < fruit.born_tt:
                problems.append(f"{fruit.fruit_id} ripens before it sets")
    if plant.laid_internodes > len(plant.stem.phytomers):
        problems.append("more internodes are laid down than the stem has")
    for phytomer in plant.stem.phytomers[: plant.laid_internodes]:
        if phytomer.leaf.stage != LeafStage.REMOVED:
            problems.append(f"{phytomer.leaf.leaf_id} is laid down with its internode")
        if phytomer.truss is not None and bears_anything(phytomer.truss):
            problems.append(f"{phytomer.truss.truss_id} is laid down still bearing")
    return problems


def _stage(organ: Organ) -> StrEnum | None:
    stage = getattr(organ, "stage", None)
    return stage if isinstance(stage, StrEnum) else None


def _allowed(before: StrEnum, after: StrEnum) -> bool:
    if before == after:
        return True
    if isinstance(before, LeafStage) and isinstance(after, LeafStage):
        return after in LEAF_CHANGES[before]
    if isinstance(before, FlowerStage) and isinstance(after, FlowerStage):
        return after in FLOWER_CHANGES[before]
    if isinstance(before, FruitStage) and isinstance(after, FruitStage):
        return after in FRUIT_CHANGES[before]
    return False


def change_problems(before: Plant, after: Plant) -> list[str]:
    """Everything wrong with `after` as a later moment of the plant `before`
    was, or nothing: time runs forward, every organ is still there, of the
    same kind and appearing when it did, and every stage has changed only as
    its kind's stages may (`LEAF_CHANGES`, `FLOWER_CHANGES`, `FRUIT_CHANGES`),
    no organ has shrunk, nor any fruit unripened, nothing laid down has stood
    up again, and the plant's history has only grown."""
    problems: list[str] = []
    if after.plant_id != before.plant_id:
        problems.append(f"{after.plant_id} is not {before.plant_id}")
    if after.thermal_time < before.thermal_time:
        problems.append("the plant's thermal time went back")
    if after.laid_internodes < before.laid_internodes:
        problems.append("laid-down internodes stood up again")
    if after.history[: len(before.history)] != before.history:
        problems.append("the plant's history was rewritten")
    later = {organ_id: (kind, organ) for kind, organ_id, _, organ in after.organs()}
    for kind, organ_id, _, organ in before.organs():
        if organ_id not in later:
            problems.append(f"{organ_id} is gone")
            continue
        later_kind, later_organ = later[organ_id]
        if later_kind != kind or later_organ.born_tt != organ.born_tt:
            problems.append(f"{organ_id} is not the organ it was")
        stage, later_stage = _stage(organ), _stage(later_organ)
        if stage is not None and later_stage is not None and not _allowed(stage, later_stage):
            problems.append(f"{organ_id} went from {stage} to {later_stage}")
        for measure in NEVER_DECREASE:
            earlier, now = getattr(organ, measure, None), getattr(later_organ, measure, None)
            if isinstance(earlier, float) and isinstance(now, float) and now < earlier:
                problems.append(f"{organ_id}'s {measure} went down")
    return problems
