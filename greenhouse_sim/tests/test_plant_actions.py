"""What a grower does to a plant: pruning, harvesting and lowering, each
kept in the plant's history, and their effects lasting through the days
after."""

import math
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.tomato.organ.actions import act
from greenhouse_sim.biology.tomato.organ.geometry import METRES_PER_CM, organ_geometry
from greenhouse_sim.biology.tomato.organ.topology import (
    FlowerStage,
    Fruit,
    FruitStage,
    HarvestFruit,
    HarvestTruss,
    LeafStage,
    LowerStem,
    Plant,
    RemoveLeaf,
    Truss,
    change_problems,
    topology_problems,
)
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.services import plants
from greenhouse_sim.services.plants import LabAction, LabRun
from greenhouse_sim.world.geometry import Vector3

# The lab's first plant on day 85: two red trusses, and more ripening above.
PLANT = plants.structure(LabRun(day=85))
UP = Vector3(x=0.0, y=0.0, z=1.0)


def _fruits(plant: Plant) -> dict[str, Fruit]:
    return {
        flower.fruit.fruit_id: flower.fruit
        for phytomer in plant.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None
    }


def _attached(plant: Plant) -> set[str]:
    """The fruits on the plant: the attached crop."""
    return {f.fruit_id for f in _fruits(plant).values() if f.stage == FruitStage.ATTACHED}


def _truss(plant: Plant, truss_id: str) -> Truss:
    return next(
        p.truss
        for p in plant.stem.phytomers
        if p.truss is not None and p.truss.truss_id == truss_id
    )


def _drawn(plant: Plant) -> set[str]:
    return {shape.organ_id for shape in organ_geometry(plant)}


def _run(day: int, *actions: tuple[int, str, str, str]) -> LabRun:
    return LabRun(
        day=day,
        actions=tuple(
            LabAction(day=on, plant_id=plant_id, kind=kind, target=target)
            for on, plant_id, kind, target in actions
        ),
    )


def test_removing_a_leaf_prunes_it_off_and_keeps_it_in_the_history() -> None:
    pruned = act(PLANT, RemoveLeaf(leaf_id="p01_n02_leaf"))
    again = act(pruned, RemoveLeaf(leaf_id="p01_n02_leaf"))
    [event] = pruned.history

    assert pruned.stem.phytomers[1].leaf.stage == LeafStage.REMOVED
    assert "p01_n02_leaf" in _drawn(PLANT) and "p01_n02_leaf" not in _drawn(pruned)
    assert (event.applied, event.note, event.organs) == (
        True,
        "removed p01_n02_leaf",
        ("p01_n02_leaf",),
    )
    assert event.thermal_time == PLANT.thermal_time
    assert again.history[-1].applied is False
    assert again.history[-1].note == "p01_n02_leaf is already removed"
    assert again.stem == pruned.stem
    assert change_problems(PLANT, again) == [] and topology_problems(again) == []


def test_a_harvested_fruit_leaves_the_attached_crop_but_not_the_history() -> None:
    fruit = _fruits(PLANT)["p01_t01_fr01"]
    picked = act(PLANT, HarvestFruit(fruit_id="p01_t01_fr01"))
    [event] = picked.history

    assert "p01_t01_fr01" in _attached(PLANT) and "p01_t01_fr01" not in _attached(picked)
    assert _fruits(picked)["p01_t01_fr01"].stage == FruitStage.HARVESTED
    assert "p01_t01_fr01" not in _drawn(picked)
    assert event.organs == ("p01_t01_fr01",)
    assert event.harvested_g == pytest.approx(fruit.mass_g)
    assert event.note == f"harvested p01_t01_fr01, {fruit.mass_g:.0f} g"
    assert change_problems(PLANT, picked) == []


def test_a_fruit_not_on_the_plant_cannot_be_harvested() -> None:
    picked = act(PLANT, HarvestFruit(fruit_id="p01_t01_fr01"))
    for plant, fruit_id, why in (
        (picked, "p01_t01_fr01", "p01_t01_fr01 is harvested, not on the plant"),
        (PLANT, "p01_t06_fr03", "p01_t06_fr03 is aborted, not on the plant"),
        (PLANT, "p01_t09_fr01", "p01 has no fruit p01_t09_fr01"),
    ):
        refused = act(plant, HarvestFruit(fruit_id=fruit_id))
        assert (refused.history[-1].applied, refused.history[-1].note) == (False, why)
        assert refused.stem == plant.stem


def test_harvesting_a_truss_picks_its_fruits_and_drops_its_flowers() -> None:
    picked = act(PLANT, HarvestTruss(truss_id="p01_t02"))
    flowering = act(PLANT, HarvestTruss(truss_id="p01_t08"))
    [event] = picked.history

    on_truss = {"p01_t02_fr01", "p01_t02_fr02", "p01_t02_fr04", "p01_t02_fr05"}
    assert on_truss <= _attached(PLANT) and not on_truss & _attached(picked)
    assert set(event.organs) == on_truss
    assert event.harvested_g == pytest.approx(sum(_fruits(PLANT)[f].mass_g for f in on_truss))
    assert "p01_t02" not in _drawn(picked)
    dropped = _truss(flowering, "p01_t08")
    assert {flower.stage for flower in dropped.flowers} == {FlowerStage.ABORTED}
    assert flowering.history[-1].note == "harvested no fruit, 0 g, dropping 5 flowers"
    assert act(picked, HarvestTruss(truss_id="p01_t02")).history[-1].note == (
        "p01_t02 bears nothing to harvest"
    )


def test_a_harvested_truss_grows_nothing_more() -> None:
    later = plants.structure(_run(90, (85, "p01", "harvest_truss", "p01_t08")))
    truss = _truss(later, "p01_t08")

    assert {flower.stage for flower in truss.flowers} == {FlowerStage.ABORTED}
    assert all(flower.fruit is None for flower in truss.flowers)


def test_the_stem_is_lowered_only_where_it_is_bare() -> None:
    refused = act(PLANT, LowerStem(internodes=2))
    bare = act(act(PLANT, RemoveLeaf(leaf_id="p01_n01_leaf")), RemoveLeaf(leaf_id="p01_n02_leaf"))
    lowered = act(bare, LowerStem(internodes=2))
    too_far = act(lowered, LowerStem(internodes=1))

    assert refused.history[-1].note == "p01_n01_leaf is still on the stem"
    assert refused.laid_internodes == 0
    assert lowered.laid_internodes == 2
    drop = sum(p.internode.length_cm for p in PLANT.stem.phytomers[:2])
    assert lowered.history[-1].note == f"laid 2 internodes down, lowering the top by {drop:.0f} cm"
    assert too_far.history[-1].note == "p01_n03_leaf is still on the stem"
    assert topology_problems(lowered) == [] and change_problems(bare, lowered) == []


def test_a_lowered_stem_lies_along_the_row_and_rises_from_where_it_ends() -> None:
    bare = act(act(PLANT, RemoveLeaf(leaf_id="p01_n01_leaf")), RemoveLeaf(leaf_id="p01_n02_leaf"))
    lowered = act(bare, LowerStem(internodes=2))
    before = {s.shape_id: s for s in organ_geometry(bare)}
    after = {s.shape_id: s for s in organ_geometry(lowered)}
    laid = sum(p.internode.length_cm for p in PLANT.stem.phytomers[:2]) * METRES_PER_CM

    for shape_id in ("p01_n01_internode", "p01_n02_internode"):
        axis = after[shape_id].transform.rotation.rotate(UP)
        assert axis.y == pytest.approx(1.0) and after[shape_id].transform.position.z == 0
    third = after["p01_n03_internode"].transform.position
    assert (third.x, third.y, third.z) == pytest.approx((0, laid, 0))
    # Everything above comes down by the laid-down length, and along the row by it.
    top_before = before["p01_n20_leaf_petiole"].transform.position
    top_after = after["p01_n20_leaf_petiole"].transform.position
    assert top_after.z == pytest.approx(top_before.z - laid)
    assert top_after.y == pytest.approx(top_before.y + laid)
    assert math.isclose(top_after.x, top_before.x, abs_tol=1e-12)


def test_scheduled_actions_last_through_the_days_after_and_not_before() -> None:
    schedule = (
        (30, "p01", "remove_leaf", "p01_n02_leaf"),
        (85, "p01", "harvest_fruit", "p01_t01_fr01"),
        # A young fruit, still growing and green.
        (85, "p01", "harvest_fruit", "p01_t05_fr01"),
    )
    before, on, picked_on, after = (
        plants.structure(_run(day, *schedule)) for day in (29, 30, 85, 90)
    )

    assert before.stem.phytomers[1].leaf.stage != LeafStage.REMOVED
    assert on.stem.phytomers[1].leaf.stage == LeafStage.REMOVED
    assert after.stem.phytomers[1].leaf.stage == LeafStage.REMOVED
    assert [event.note.split(",")[0] for event in after.history] == [
        "removed p01_n02_leaf",
        "harvested p01_t01_fr01",
        "harvested p01_t05_fr01",
    ]
    assert [event.thermal_time for event in after.history] == [560.0, 1165.0, 1165.0]
    # A picked fruit stays as it was when picked, though the days go on.
    for fruit_id in ("p01_t01_fr01", "p01_t05_fr01"):
        assert _fruits(after)[fruit_id] == _fruits(picked_on)[fruit_id]
        assert fruit_id not in _attached(after)
    still_growing = _fruits(plants.structure(_run(90)))["p01_t05_fr01"]
    assert still_growing.mass_g > _fruits(after)["p01_t05_fr01"].mass_g
    assert change_problems(on, after) == []


def test_the_lab_schedules_actions_from_its_query_and_shows_them() -> None:
    query = "day=40&act=30:p01:remove_leaf:p01_n02_leaf&act=35:p02:remove_leaf:p02_n01_leaf"
    scene = SceneSnapshot.model_validate(respond("GET", f"/api/plants/scene?{query}").body)
    structure = Plant.model_validate(respond("GET", f"/api/plants/structure?{query}").body)
    ids = {entity.entity_id for entity in scene.entities}

    assert "p01_n02_leaf_petiole" not in ids and "p02_n01_leaf_petiole" not in ids
    assert "p01_n03_leaf_petiole" in ids
    assert [event.note for event in structure.history] == ["removed p01_n02_leaf"]


@pytest.mark.parametrize(
    ("act_query", "reason"),
    [
        ("30-p01-remove_leaf", "act wants day:plant:action:organ, not '30-p01-remove_leaf'"),
        (
            "soon:p01:remove_leaf:p01_n02_leaf",
            "act wants day:plant:action:organ, not 'soon:p01:remove_leaf:p01_n02_leaf'",
        ),
        (
            "30:p01:water:p01_n02_leaf",
            "the plant lab has no action 'water', "
            "only remove_leaf, harvest_fruit, harvest_truss, lower_stem",
        ),
        ("30:p99:remove_leaf:p99_n02_leaf", "the plant lab has no plant 'p99' to act on"),
        ("30:p01:lower_stem:far", "lower_stem wants how many internodes, not 'far'"),
        ("91:p01:remove_leaf:p01_n02_leaf", "the plant lab runs from day 0 to day 90, not day 91"),
    ],
)
def test_an_action_the_lab_cannot_schedule_is_refused(act_query: str, reason: str) -> None:
    answer = respond("GET", f"/api/plants/scene?act={act_query}")

    assert (answer.status, answer.body) == (HTTPStatus.BAD_REQUEST, {"error": reason})


def test_a_rewritten_history_or_a_stem_stood_up_again_is_found_out() -> None:
    pruned = act(PLANT, RemoveLeaf(leaf_id="p01_n01_leaf"))
    lowered = act(pruned, LowerStem(internodes=1))

    assert change_problems(pruned, PLANT) == [
        "the plant's history was rewritten",
        "p01_n01_leaf went from removed to mature",
    ]
    assert change_problems(lowered, pruned.model_copy(update={"history": lowered.history})) == [
        "laid-down internodes stood up again"
    ]
    assert topology_problems(PLANT.model_copy(update={"laid_internodes": 1})) == [
        "p01_n01_leaf is laid down with its internode"
    ]
