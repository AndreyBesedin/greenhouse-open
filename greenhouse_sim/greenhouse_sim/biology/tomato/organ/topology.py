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
accumulated since. `topology_problems` lists whatever breaks the structure's
rules, so tests, and later the model itself, can hold every plant to them.
"""

from collections import Counter
from collections.abc import Iterator
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveInt


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

    GROWING = "growing"
    HARVESTED = "harvested"


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
    stage: FruitStage = FruitStage.GROWING


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


class Plant(Organ):
    """One plant, organ by organ, and the thermal time it has accumulated."""

    plant_id: str
    thermal_time: NonNegativeFloat
    stem: Axis

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
    return problems
