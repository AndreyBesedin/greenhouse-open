"""A reference young tomato plant, built by hand from fixed sizes.

The development model grows plants from thermal time (`development`); this
one is built by hand, with a truss the model does not yet grow (P03.5), for
the tests to hold to the topology's rules and to draw: nine phytomers, a
phyllochron apart, the first truss on the ninth with six flower buds. Its
sizes are typical of a transplant a few weeks old: its lower phytomers full
grown, and its youngest still growing, each in proportion to its thermal age.
"""

from typing import Final

from greenhouse_sim.biology.tomato.organ.topology import (
    Axis,
    Flower,
    Internode,
    Leaf,
    LeafStage,
    Phytomer,
    Plant,
    Truss,
    flower_id,
    internode_id,
    leaf_id,
    phytomer_id,
    stem_id,
    truss_id,
)

PHYTOMERS: Final = 9
# Thermal time between one phytomer's appearance and the next's, in °Cd.
PHYLLOCHRON_CD: Final = 33.0
# A full-grown phytomer's sizes.
INTERNODE_LENGTH_CM: Final = 6.0
INTERNODE_DIAMETER_MM: Final = 9.0
LEAF_LENGTH_CM: Final = 30.0
# The first truss appears on this phytomer, with this many flower buds.
FIRST_TRUSS_RANK: Final = 9
FLOWERS_PER_TRUSS: Final = 6
# The youngest phytomers are still growing: a phytomer reaches its full size
# when this many younger ones have appeared.
MATURE_BELOW: Final = 3
# A growing internode is at least this share of its full diameter.
YOUNG_DIAMETER_FRACTION: Final = 0.6


def grown_fraction(age_cd: float) -> float:
    """How much of its full size a phytomer of this thermal age has reached:
    a share of it for every phyllochron of its age, and one more for its
    first, until it is full grown."""
    return min(1.0, (age_cd / PHYLLOCHRON_CD + 1) / (MATURE_BELOW + 1))


def young_plant(plant_id: str) -> Plant:
    """The reference young plant, its youngest phytomer just appeared."""
    thermal_time = (PHYTOMERS - 1) * PHYLLOCHRON_CD
    phytomers = []
    trusses = 0
    for rank in range(1, PHYTOMERS + 1):
        born = (rank - 1) * PHYLLOCHRON_CD
        truss = None
        if rank >= FIRST_TRUSS_RANK:
            trusses += 1
            truss = Truss(
                truss_id=truss_id(plant_id, trusses),
                number=trusses,
                born_tt=born,
                final_flower_count=FLOWERS_PER_TRUSS,
                flowers=tuple(
                    Flower(flower_id=flower_id(plant_id, trusses, place), rank=place, born_tt=born)
                    for place in range(1, FLOWERS_PER_TRUSS + 1)
                ),
            )
        grown = grown_fraction(thermal_time - born)
        diameter = YOUNG_DIAMETER_FRACTION + (1 - YOUNG_DIAMETER_FRACTION) * grown
        phytomers.append(
            Phytomer(
                phytomer_id=phytomer_id(plant_id, rank),
                rank=rank,
                born_tt=born,
                internode=Internode(
                    internode_id=internode_id(plant_id, rank),
                    born_tt=born,
                    length_cm=INTERNODE_LENGTH_CM * grown,
                    diameter_mm=INTERNODE_DIAMETER_MM * diameter,
                    final_length_cm=INTERNODE_LENGTH_CM,
                    final_diameter_mm=INTERNODE_DIAMETER_MM,
                ),
                leaf=Leaf(
                    leaf_id=leaf_id(plant_id, rank),
                    born_tt=born,
                    length_cm=LEAF_LENGTH_CM * grown,
                    final_length_cm=LEAF_LENGTH_CM,
                    stage=LeafStage.MATURE if grown == 1.0 else LeafStage.EXPANDING,
                ),
                truss=truss,
            )
        )
    return Plant(
        plant_id=plant_id,
        born_tt=0.0,
        thermal_time=thermal_time,
        stem=Axis(axis_id=stem_id(plant_id), born_tt=0.0, phytomers=tuple(phytomers)),
    )
