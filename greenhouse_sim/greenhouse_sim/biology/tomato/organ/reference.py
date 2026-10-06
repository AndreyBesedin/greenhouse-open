"""A reference young tomato plant, built by hand from fixed sizes.

Until the model grows plants itself from thermal time (P03.3), this is the
plant the lab shows and the tests hold to the topology's rules: nine
phytomers, a phyllochron apart, the first truss on the ninth with six flower
buds. Its sizes are typical of a transplant a few weeks old.
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
INTERNODE_LENGTH_CM: Final = 6.0
INTERNODE_DIAMETER_MM: Final = 9.0
LEAF_LENGTH_CM: Final = 30.0
# The first truss appears on this phytomer, with this many flower buds.
FIRST_TRUSS_RANK: Final = 9
FLOWERS_PER_TRUSS: Final = 6
# Leaves this many phytomers below the youngest have finished expanding.
MATURE_BELOW: Final = 3


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
                flowers=tuple(
                    Flower(flower_id=flower_id(plant_id, trusses, place), rank=place, born_tt=born)
                    for place in range(1, FLOWERS_PER_TRUSS + 1)
                ),
            )
        mature = rank <= PHYTOMERS - MATURE_BELOW
        phytomers.append(
            Phytomer(
                phytomer_id=phytomer_id(plant_id, rank),
                rank=rank,
                born_tt=born,
                internode=Internode(
                    internode_id=internode_id(plant_id, rank),
                    born_tt=born,
                    length_cm=INTERNODE_LENGTH_CM,
                    diameter_mm=INTERNODE_DIAMETER_MM,
                ),
                leaf=Leaf(
                    leaf_id=leaf_id(plant_id, rank),
                    born_tt=born,
                    length_cm=LEAF_LENGTH_CM,
                    stage=LeafStage.MATURE if mature else LeafStage.EXPANDING,
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
