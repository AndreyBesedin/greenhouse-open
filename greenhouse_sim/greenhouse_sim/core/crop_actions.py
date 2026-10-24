"""What a crop action does to a plant of the organ crop (P13.5, decision 0046).

A crop action of the protocol (`greenhouse_protocol.actions`), a harvest, a
lowering or a leaf removed, is carried out on a plant as the organ model's
own operations on it (`PlantOperation`), each an event in its history, done
or refused, as the organ model has it
(`greenhouse_sim.biology.tomato.organ.actions`). The operations are the
crop's inner steps, not actions: no one proposes or plans them, and they
report no outcome. The action reports one: what it did, or why it was
refused.

- **A harvest** of one fruit or one truss is that operation. A harvest of
  every ripe fruit is a harvest round: every red fruit on the plant picked,
  each a harvest of its own, from its lowest truss up. It is done even when
  nothing is red: it picked nothing.
- **A lowering** by so many internodes lays them down, if they are bare. By
  so many centimetres, or to so much head room under the plant's wire, it is
  a lowering round, as a grower lowers a high-wire crop: as few of its
  lowest standing internodes as bring its top low enough, stripped of their
  leaves first, but never one whose truss still bears, nor its top one. It
  is done even when none can be laid down: it lowered the top by nothing. A
  plant that hangs from no wire cannot be lowered to a head room under one.
- **A leaf removed** is that operation.

What it did is the protocol's effect of its kind: the fruits it picked and
their fresh mass, how far it lowered the top as the plant is trained, the
leaf it removed.
"""

from dataclasses import dataclass

from greenhouse_protocol.actions import Harvest, HarvestScope, Lower, RemoveLeaf
from greenhouse_protocol.outcome import Harvested, LeafRemoved, Lowered

from greenhouse_sim.biology.tomato.organ import topology
from greenhouse_sim.biology.tomato.organ.actions import act, harvest_round, lowering_round
from greenhouse_sim.biology.tomato.organ.geometry import (
    ALONG_THE_ROW,
    METRES_PER_CM,
    top_height_m,
)
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.domain.organs import FruitStage
from greenhouse_sim.world.training import Training

# The crop actions the organ crop carries out.
type CropAction = Harvest | Lower | RemoveLeaf
type CropEffect = Harvested | Lowered | LeafRemoved


@dataclass(frozen=True)
class CarriedOut[PlantT]:
    """A crop action carried out on a plant: the plant after it, an organ
    crop's history longer by the operations it was done by, and either what
    it did or why it was refused."""

    plant: PlantT
    effect: CropEffect | None = None
    refusal: str | None = None


def carry_out(
    plant: Plant, action: CropAction, training: Training | None = None
) -> CarriedOut[Plant]:
    """The crop action carried out on its plant, trained as `training` says,
    or straight along its row and hanging from no wire if it is not given:
    see the module."""
    if action.plant_id != plant.plant_id:
        raise ValueError(f"an action on {action.plant_id} is not carried out on {plant.plant_id}")
    match action:
        case Harvest():
            return _harvested(plant, _harvest(plant, action))
        case Lower():
            return _lower(plant, action, training)
        case RemoveLeaf():
            after = act(plant, topology.RemoveLeaf(leaf_id=action.leaf_id))
            return _outcome(plant, after, LeafRemoved(leaf_id=action.leaf_id))


def _harvest(plant: Plant, action: Harvest) -> Plant:
    # A harvest names its organ for a fruit or a truss, and none for every
    # ripe fruit.
    if action.organ_id is None:
        return harvest_round(plant)
    if action.scope == HarvestScope.TRUSS:
        return act(plant, topology.HarvestTruss(truss_id=action.organ_id))
    return act(plant, topology.HarvestFruit(fruit_id=action.organ_id))


def _harvested(before: Plant, after: Plant) -> CarriedOut[Plant]:
    picked = _picked(after) - _picked(before)
    events = after.history[len(before.history) :]
    effect = Harvested(
        fruit_count=len(picked), fresh_mass_g=sum(event.harvested_g for event in events)
    )
    return _outcome(before, after, effect)


def _picked(plant: Plant) -> set[str]:
    """The fruits picked off the plant."""
    return {
        flower.fruit.fruit_id
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None and flower.fruit.stage == FruitStage.HARVESTED
    }


def _lower(plant: Plant, action: Lower, training: Training | None) -> CarriedOut[Plant]:
    path = ALONG_THE_ROW if training is None else training.path
    if action.by_internodes is not None:
        after = act(plant, topology.LowerStem(internodes=action.by_internodes))
    elif action.by_cm is not None:
        after = lowering_round(
            plant, top_height_m(plant, path) - action.by_cm * METRES_PER_CM, path
        )
    elif training is None or training.wire_m is None:
        return CarriedOut(plant, refusal=f"{plant.plant_id} hangs from no wire")
    else:
        # A lowering gives exactly one measure: here, its head room.
        head_room_m = action.to_head_room_m or 0.0
        after = lowering_round(plant, training.wire_m - head_room_m, path)
    # How far its top came down, as its training holds it: on a high wire
    # the standing stem leans, and leans otherwise once it is first lowered,
    # so not as far as the stem laid down. Never up: by nothing at least.
    drop_m = top_height_m(plant, path) - top_height_m(after, path)
    return _outcome(plant, after, Lowered(by_cm=max(0.0, drop_m) / METRES_PER_CM))


def _outcome(before: Plant, after: Plant, effect: CropEffect) -> CarriedOut[Plant]:
    """Done, with its effect, unless an operation it was done by was refused:
    then refused, as that operation was."""
    events = after.history[len(before.history) :]
    refused = next((event for event in events if not event.applied), None)
    if refused is not None:
        return CarriedOut(after, refusal=refused.note)
    return CarriedOut(after, effect=effect)
