"""What a grower does to a plant: prune, harvest and lower.

These are the organ model's operations on a plant (`PlantOperation`), which
a run's crop actions are carried out as
(`greenhouse_sim.core.crop_actions`); they are not actions themselves. Every
operation asked of a plant becomes an event in its history, at the plant's
thermal time: applied, saying what it did, or refused, saying why. Nothing
an operation touches leaves the plant's structure. A removed leaf, a
picked fruit and a dropped flower keep their places and identifiers, with
their stages saying they are no longer on the plant, so the history can
always name them.

- Removing a leaf prunes it off, unless it already is.
- Harvesting a fruit picks it while it is on the plant, at the size and
  ripeness it has then.
- Harvesting a truss picks all of its fruits and drops the flowers it still
  bears, so nothing more grows on it.
- Lowering the stem lays its lowest standing internodes down along the row,
  so its top comes down by their length. Only bare internodes can be laid
  down: their leaves removed and their trusses bearing nothing.

A harvest round (`harvest_round`) picks every red fruit on a plant, each
fruit its own harvest, from its lowest truss up. A lowering round
(`lowering_round`) keeps a plant's top under its wire, as a grower lowers a
high-wire crop: it lays down as few of its lowest standing internodes as
bring its top low enough, stripping their leaves first, but never one whose
truss still bears.
"""

from greenhouse_sim.biology.plant.organs import Flower
from greenhouse_sim.biology.tomato.organ.fruit import Maturity, maturity
from greenhouse_sim.biology.tomato.organ.geometry import ALONG_THE_ROW, StemPath, top_height_m
from greenhouse_sim.biology.tomato.organ.topology import (
    HarvestFruit,
    HarvestTruss,
    LowerStem,
    Phytomer,
    Plant,
    PlantEvent,
    PlantOperation,
    RemoveLeaf,
    Truss,
    bears_anything,
)
from greenhouse_sim.domain.organs import FlowerStage, FruitStage, LeafStage


def _event(plant: Plant, operation: PlantOperation, note: str, **outcome: object) -> PlantEvent:
    return PlantEvent.model_validate(
        {
            "thermal_time": plant.thermal_time,
            "action": operation,
            "applied": bool(outcome.pop("applied", False)),
            "note": note,
            **outcome,
        }
    )


def _with(plant: Plant, index: int, phytomer: Phytomer, event: PlantEvent) -> Plant:
    phytomers = list(plant.stem.phytomers)
    phytomers[index] = phytomer
    stem = plant.stem.model_copy(update={"phytomers": tuple(phytomers)})
    return plant.model_copy(update={"stem": stem, "history": (*plant.history, event)})


def _refused(plant: Plant, operation: PlantOperation, why: str) -> Plant:
    return plant.model_copy(update={"history": (*plant.history, _event(plant, operation, why))})


def _remove_leaf(plant: Plant, operation: RemoveLeaf) -> Plant:
    for index, phytomer in enumerate(plant.stem.phytomers):
        leaf = phytomer.leaf
        if leaf.leaf_id != operation.leaf_id:
            continue
        if leaf.stage == LeafStage.REMOVED:
            return _refused(plant, operation, f"{leaf.leaf_id} is already removed")
        removed = phytomer.model_copy(
            update={"leaf": leaf.model_copy(update={"stage": LeafStage.REMOVED})}
        )
        event = _event(
            plant, operation, f"removed {leaf.leaf_id}", applied=True, organs=(leaf.leaf_id,)
        )
        return _with(plant, index, removed, event)
    return _refused(plant, operation, f"{plant.plant_id} has no leaf {operation.leaf_id}")


def _picked(flower: Flower) -> Flower:
    """The flower with its fruit picked, if it bears one on the plant, or
    dropped if it is still a bud or open."""
    fruit = flower.fruit
    if fruit is not None and fruit.stage == FruitStage.ATTACHED:
        return flower.model_copy(
            update={"fruit": fruit.model_copy(update={"stage": FruitStage.HARVESTED})}
        )
    if flower.stage in {FlowerStage.BUD, FlowerStage.OPEN}:
        return flower.model_copy(update={"stage": FlowerStage.ABORTED})
    return flower


def _cut(
    plant: Plant, operation: PlantOperation, index: int, truss: Truss, picks: set[str]
) -> Plant:
    """The plant with these of the truss's flowers and fruits picked or
    dropped, and the event saying so."""
    flowers = tuple(
        _picked(flower) if flower.flower_id in picks else flower for flower in truss.flowers
    )
    changed = [
        (before, after)
        for before, after in zip(truss.flowers, flowers, strict=True)
        if before != after
    ]
    fruits = [
        after.fruit
        for _, after in changed
        if after.fruit is not None and after.fruit.stage == FruitStage.HARVESTED
    ]
    harvested_g = sum(fruit.mass_g for fruit in fruits)
    organs = tuple(
        after.fruit.fruit_id if after.fruit is not None else after.flower_id for _, after in changed
    )
    dropped = len(changed) - len(fruits)
    picked = ", ".join(fruit.fruit_id for fruit in fruits) or "no fruit"
    note = f"harvested {picked}, {harvested_g:.0f} g" + (
        f", dropping {dropped} flowers" if dropped else ""
    )
    phytomer = plant.stem.phytomers[index]
    cut = phytomer.model_copy(update={"truss": truss.model_copy(update={"flowers": flowers})})
    event = _event(plant, operation, note, applied=True, organs=organs, harvested_g=harvested_g)
    return _with(plant, index, cut, event)


def _harvest_fruit(plant: Plant, operation: HarvestFruit) -> Plant:
    for index, phytomer in enumerate(plant.stem.phytomers):
        truss = phytomer.truss
        if truss is None:
            continue
        for flower in truss.flowers:
            fruit = flower.fruit
            if fruit is None or fruit.fruit_id != operation.fruit_id:
                continue
            if fruit.stage != FruitStage.ATTACHED:
                return _refused(
                    plant, operation, f"{fruit.fruit_id} is {fruit.stage}, not on the plant"
                )
            return _cut(plant, operation, index, truss, {flower.flower_id})
    return _refused(plant, operation, f"{plant.plant_id} has no fruit {operation.fruit_id}")


def _harvest_truss(plant: Plant, operation: HarvestTruss) -> Plant:
    for index, phytomer in enumerate(plant.stem.phytomers):
        truss = phytomer.truss
        if truss is None or truss.truss_id != operation.truss_id:
            continue
        if not bears_anything(truss):
            return _refused(plant, operation, f"{truss.truss_id} bears nothing to harvest")
        return _cut(plant, operation, index, truss, {flower.flower_id for flower in truss.flowers})
    return _refused(plant, operation, f"{plant.plant_id} has no truss {operation.truss_id}")


def _lower_stem(plant: Plant, operation: LowerStem) -> Plant:
    standing = plant.stem.phytomers[plant.laid_internodes :]
    if len(standing) <= operation.internodes:
        return _refused(
            plant, operation, f"{plant.plant_id} has only {len(standing)} internodes standing"
        )
    lowered = standing[: operation.internodes]
    for phytomer in lowered:
        if phytomer.leaf.stage != LeafStage.REMOVED:
            return _refused(plant, operation, f"{phytomer.leaf.leaf_id} is still on the stem")
        if phytomer.truss is not None and bears_anything(phytomer.truss):
            return _refused(plant, operation, f"{phytomer.truss.truss_id} still bears")
    drop_cm = sum(phytomer.internode.length_cm for phytomer in lowered)
    organs = tuple(phytomer.internode.internode_id for phytomer in lowered)
    note = f"laid {operation.internodes} internodes down, lowering the top by {drop_cm:.0f} cm"
    event = _event(plant, operation, note, applied=True, organs=organs)
    return plant.model_copy(
        update={
            "laid_internodes": plant.laid_internodes + operation.internodes,
            "history": (*plant.history, event),
        }
    )


def act(plant: Plant, operation: PlantOperation) -> Plant:
    """The plant after this operation is asked of it: changed if it can be done,
    and either way one event longer in its history."""
    match operation:
        case RemoveLeaf():
            return _remove_leaf(plant, operation)
        case HarvestFruit():
            return _harvest_fruit(plant, operation)
        case HarvestTruss():
            return _harvest_truss(plant, operation)
        case LowerStem():
            return _lower_stem(plant, operation)


def harvest_round(plant: Plant) -> Plant:
    """The plant after a harvest round: every red fruit on it picked, each a
    harvest of its own in its history, from its lowest truss up; unchanged
    if it bears none."""
    red = [
        flower.fruit.fruit_id
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None
        and flower.fruit.stage == FruitStage.ATTACHED
        and maturity(flower.fruit.ripeness) == Maturity.RED
    ]
    for fruit_id in red:
        plant = act(plant, HarvestFruit(fruit_id=fruit_id))
    return plant


def lowering_round(plant: Plant, most_m: float, path: StemPath = ALONG_THE_ROW) -> Plant:
    """The plant after a lowering round: if its top stands more than
    `most_m` above its foot, as `path` trains it, its lowest standing
    internodes laid down until it stands no higher, each stripped of its
    leaf first, but never one whose truss still bears, nor its top one;
    unchanged otherwise."""
    if top_height_m(plant, path) <= most_m:
        return plant
    standing = plant.stem.phytomers[plant.laid_internodes : -1]
    count = 0
    for phytomer in standing:
        if phytomer.truss is not None and bears_anything(phytomer.truss):
            break
        count += 1
        if top_height_m(plant, path, plant.laid_internodes + count) <= most_m:
            break
    if count == 0:
        return plant
    for phytomer in standing[:count]:
        if phytomer.leaf.stage != LeafStage.REMOVED:
            plant = act(plant, RemoveLeaf(leaf_id=phytomer.leaf.leaf_id))
    return act(plant, LowerStem(internodes=count))
