"""Crop actions carried out on a plant of the organ crop (P13.5): each as the
organ model's own operations, each kept in the plant's history, and what it
did, or why it was refused."""

from typing import Final

import pytest
from greenhouse_protocol.actions import Harvest, HarvestScope, Lower, RemoveLeaf
from greenhouse_protocol.outcome import Harvested, LeafRemoved, Lowered

from greenhouse_sim.biology.tomato.organ import topology
from greenhouse_sim.biology.tomato.organ.actions import act, harvest_round, lowering_round
from greenhouse_sim.biology.tomato.organ.geometry import ALONG_THE_ROW, METRES_PER_CM, top_height_m
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.core.crop import CropWork
from greenhouse_sim.core.crop_actions import carry_out
from greenhouse_sim.services import plants
from greenhouse_sim.services.plants import LabRun
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.rows import PlantingPosition
from greenhouse_sim.world.training import Training

# The lab's first plant on day 85: two red trusses, and more ripening above.
PLANT: Final = plants.structure(LabRun(day=85))
# The same plant with its red fruit picked, so that its lowest trusses bear
# nothing and its stem can be laid down past them.
PICKED: Final = harvest_round(PLANT)
# The plant hanging from a wire as high as its top stands.
WIRED: Final = Training(
    position=PlantingPosition(position_id="r1_p1", row=1, index=1, point=Vector3(x=0, y=0, z=0)),
    path=ALONG_THE_ROW,
    wire_m=top_height_m(PLANT),
)


def _laid_cm(before: Plant, after: Plant) -> float:
    laid = after.stem.phytomers[before.laid_internodes : after.laid_internodes]
    return sum(phytomer.internode.length_cm for phytomer in laid)


def test_a_leaf_removed_is_the_organ_model_s_pruning() -> None:
    removal = RemoveLeaf(plant_id="p01", leaf_id="p01_n02_leaf")
    done = carry_out(PLANT, removal)
    again = carry_out(done.plant, removal)

    assert done.plant == act(PLANT, topology.RemoveLeaf(leaf_id="p01_n02_leaf"))
    assert (done.effect, done.refusal) == (LeafRemoved(leaf_id="p01_n02_leaf"), None)
    assert (again.effect, again.refusal) == (None, "p01_n02_leaf is already removed")
    assert again.plant.history[-1].applied is False


def test_a_harvest_of_a_fruit_or_a_truss_is_its_operation_and_says_what_it_picked() -> None:
    fruit = Harvest(plant_id="p01", scope=HarvestScope.FRUIT, organ_id="p01_t01_fr01")
    picked = carry_out(PLANT, fruit)
    cut = carry_out(PLANT, Harvest(plant_id="p01", scope=HarvestScope.TRUSS, organ_id="p01_t02"))
    flowering = carry_out(
        PLANT, Harvest(plant_id="p01", scope=HarvestScope.TRUSS, organ_id="p01_t08")
    )

    assert picked.plant == act(PLANT, topology.HarvestFruit(fruit_id="p01_t01_fr01"))
    assert cut.plant == act(PLANT, topology.HarvestTruss(truss_id="p01_t02"))
    assert picked.effect == Harvested(
        fruit_count=1, fresh_mass_g=picked.plant.history[-1].harvested_g
    )
    assert cut.effect == Harvested(fruit_count=4, fresh_mass_g=cut.plant.history[-1].harvested_g)
    # A truss still in flower is cut, its flowers dropped: no fruit picked.
    assert flowering.effect == Harvested(fruit_count=0, fresh_mass_g=0.0)
    refused = carry_out(picked.plant, fruit)
    assert (refused.effect, refused.refusal) == (
        None,
        "p01_t01_fr01 is harvested, not on the plant",
    )


def test_a_harvest_of_every_ripe_fruit_is_a_harvest_round_done_even_when_none_is_ripe() -> None:
    ripe = Harvest(plant_id="p01", scope=HarvestScope.RIPE)
    done = carry_out(PLANT, ripe)
    again = carry_out(done.plant, ripe)

    assert done.plant == PICKED
    assert done.effect == Harvested(
        fruit_count=len(PICKED.history),
        fresh_mass_g=sum(event.harvested_g for event in PICKED.history),
    )
    assert (again.plant, again.effect) == (PICKED, Harvested(fruit_count=0, fresh_mass_g=0.0))


def test_a_lowering_by_internodes_lays_them_down_if_they_are_bare() -> None:
    lowering = Lower(plant_id="p01", by_internodes=2)
    bare = act(
        act(PLANT, topology.RemoveLeaf(leaf_id="p01_n01_leaf")),
        topology.RemoveLeaf(leaf_id="p01_n02_leaf"),
    )
    lowered = carry_out(bare, lowering)
    refused = carry_out(PLANT, lowering)

    assert lowered.plant == act(bare, topology.LowerStem(internodes=2))
    drop = sum(phytomer.internode.length_cm for phytomer in PLANT.stem.phytomers[:2])
    assert lowered.effect == Lowered(by_cm=drop)
    assert (refused.effect, refused.refusal) == (None, "p01_n01_leaf is still on the stem")
    assert refused.plant.laid_internodes == 0


def test_a_lowering_to_a_head_room_is_a_lowering_round_under_the_plant_s_wire() -> None:
    lowering = Lower(plant_id="p01", to_head_room_m=0.3)
    lowered = carry_out(PICKED, lowering, WIRED)
    again = carry_out(lowered.plant, lowering, WIRED)
    unwired = carry_out(PICKED, lowering)

    assert lowered.plant == lowering_round(PICKED, top_height_m(PLANT) - 0.3, ALONG_THE_ROW)
    assert lowered.plant.laid_internodes > 0
    assert lowered.effect == Lowered(by_cm=_laid_cm(PICKED, lowered.plant))
    # Low enough already: done, lowering it by nothing.
    assert (again.plant, again.effect) == (lowered.plant, Lowered(by_cm=0.0))
    # A plant that hangs from no wire is left as it is.
    assert (unwired.plant, unwired.effect, unwired.refusal) == (
        PICKED,
        None,
        "p01 hangs from no wire",
    )


def test_a_lowering_by_centimetres_lays_down_as_few_internodes_as_bring_the_top_that_far() -> None:
    lowered = carry_out(PICKED, Lower(plant_id="p01", by_cm=10.0))
    laid = lowered.plant.laid_internodes

    assert lowered.plant == lowering_round(PICKED, top_height_m(PICKED) - 10.0 * METRES_PER_CM)
    assert lowered.effect == Lowered(by_cm=_laid_cm(PICKED, lowered.plant))
    assert top_height_m(PICKED) - top_height_m(lowered.plant) >= 10.0 * METRES_PER_CM
    assert top_height_m(PICKED) - top_height_m(PICKED, laid=laid - 1) < 10.0 * METRES_PER_CM


def test_an_action_on_another_plant_is_not_carried_out_on_this_one() -> None:
    with pytest.raises(ValueError, match="an action on p02 is not carried out on p01"):
        carry_out(PLANT, RemoveLeaf(plant_id="p02", leaf_id="p02_n01_leaf"))


def test_crop_work_is_its_crop_actions_on_the_days_they_are_due() -> None:
    work = CropWork(harvest_every_days=7, lower_every_days=14, head_room_m=0.25)
    harvest = Harvest(plant_id="p01", scope=HarvestScope.RIPE)

    assert work.actions_on(14, "p01") == [harvest, Lower(plant_id="p01", to_head_room_m=0.25)]
    assert work.actions_on(7, "p01") == [harvest]
    assert work.actions_on(0, "p01") == work.actions_on(3, "p01") == []
    assert CropWork().actions_on(14, "p01") == []
