"""What a grower does to a plant: prune, harvest and lower.

Every action asked of a plant becomes an event in its history, at the
plant's thermal time: applied, saying what it did, or refused, saying why.
Nothing an action touches leaves the plant's structure. A removed leaf, a
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
"""

from greenhouse_sim.biology.tomato.organ.topology import (
    Flower,
    FlowerStage,
    FruitStage,
    HarvestFruit,
    HarvestTruss,
    LeafStage,
    LowerStem,
    Phytomer,
    Plant,
    PlantAction,
    PlantEvent,
    RemoveLeaf,
    Truss,
    bears_anything,
)


def _event(plant: Plant, action: PlantAction, note: str, **outcome: object) -> PlantEvent:
    return PlantEvent.model_validate(
        {
            "thermal_time": plant.thermal_time,
            "action": action,
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


def _refused(plant: Plant, action: PlantAction, why: str) -> Plant:
    return plant.model_copy(update={"history": (*plant.history, _event(plant, action, why))})


def _remove_leaf(plant: Plant, action: RemoveLeaf) -> Plant:
    for index, phytomer in enumerate(plant.stem.phytomers):
        leaf = phytomer.leaf
        if leaf.leaf_id != action.leaf_id:
            continue
        if leaf.stage == LeafStage.REMOVED:
            return _refused(plant, action, f"{leaf.leaf_id} is already removed")
        removed = phytomer.model_copy(
            update={"leaf": leaf.model_copy(update={"stage": LeafStage.REMOVED})}
        )
        event = _event(
            plant, action, f"removed {leaf.leaf_id}", applied=True, organs=(leaf.leaf_id,)
        )
        return _with(plant, index, removed, event)
    return _refused(plant, action, f"{plant.plant_id} has no leaf {action.leaf_id}")


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


def _cut(plant: Plant, action: PlantAction, index: int, truss: Truss, picks: set[str]) -> Plant:
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
    event = _event(plant, action, note, applied=True, organs=organs, harvested_g=harvested_g)
    return _with(plant, index, cut, event)


def _harvest_fruit(plant: Plant, action: HarvestFruit) -> Plant:
    for index, phytomer in enumerate(plant.stem.phytomers):
        truss = phytomer.truss
        if truss is None:
            continue
        for flower in truss.flowers:
            fruit = flower.fruit
            if fruit is None or fruit.fruit_id != action.fruit_id:
                continue
            if fruit.stage != FruitStage.ATTACHED:
                return _refused(
                    plant, action, f"{fruit.fruit_id} is {fruit.stage}, not on the plant"
                )
            return _cut(plant, action, index, truss, {flower.flower_id})
    return _refused(plant, action, f"{plant.plant_id} has no fruit {action.fruit_id}")


def _harvest_truss(plant: Plant, action: HarvestTruss) -> Plant:
    for index, phytomer in enumerate(plant.stem.phytomers):
        truss = phytomer.truss
        if truss is None or truss.truss_id != action.truss_id:
            continue
        if not bears_anything(truss):
            return _refused(plant, action, f"{truss.truss_id} bears nothing to harvest")
        return _cut(plant, action, index, truss, {flower.flower_id for flower in truss.flowers})
    return _refused(plant, action, f"{plant.plant_id} has no truss {action.truss_id}")


def _lower_stem(plant: Plant, action: LowerStem) -> Plant:
    standing = plant.stem.phytomers[plant.laid_internodes :]
    if len(standing) <= action.internodes:
        return _refused(
            plant, action, f"{plant.plant_id} has only {len(standing)} internodes standing"
        )
    lowered = standing[: action.internodes]
    for phytomer in lowered:
        if phytomer.leaf.stage != LeafStage.REMOVED:
            return _refused(plant, action, f"{phytomer.leaf.leaf_id} is still on the stem")
        if phytomer.truss is not None and bears_anything(phytomer.truss):
            return _refused(plant, action, f"{phytomer.truss.truss_id} still bears")
    drop_cm = sum(phytomer.internode.length_cm for phytomer in lowered)
    organs = tuple(phytomer.internode.internode_id for phytomer in lowered)
    note = f"laid {action.internodes} internodes down, lowering the top by {drop_cm:.0f} cm"
    event = _event(plant, action, note, applied=True, organs=organs)
    return plant.model_copy(
        update={
            "laid_internodes": plant.laid_internodes + action.internodes,
            "history": (*plant.history, event),
        }
    )


def act(plant: Plant, action: PlantAction) -> Plant:
    """The plant after this action is asked of it: changed if it can be done,
    and either way one event longer in its history."""
    match action:
        case RemoveLeaf():
            return _remove_leaf(plant, action)
        case HarvestFruit():
            return _harvest_fruit(plant, action)
        case HarvestTruss():
            return _harvest_truss(plant, action)
        case LowerStem():
            return _lower_stem(plant, action)
