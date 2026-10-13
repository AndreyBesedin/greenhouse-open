"""How a high-wire crop is trained and lowered (P09.3): a pair of wires above
each row, plants trained to them by turns, a lowering round that strips and
lays down a stem's bare lower part, and the lane round the gutter the laid
stems lie in, passing round the row's ends as a carousel."""

import math
from collections.abc import Sequence

import pytest

from greenhouse_sim.biology.tomato.organ.actions import act, lowering_round
from greenhouse_sim.biology.tomato.organ.geometry import (
    ALONG_THE_ROW,
    laid_length_m,
    organ_geometry,
    rising_point,
    stem_height_m,
    top_height_m,
)
from greenhouse_sim.biology.tomato.organ.topology import HarvestTruss
from greenhouse_sim.biology.tomato.organ.transplants import transplant
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import CropWork, RunCrop
from greenhouse_sim.core.timeline import HARVEST_ROUND, LOWERING_ROUND, RunProcesses, events
from greenhouse_sim.domain.organs import LeafStage
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import plants as lab
from greenhouse_sim.solar.plants import Crown
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import TOMATO_GUTTER, CropRows, CropWires
from greenhouse_sim.world.training import AlongItsRow, HighWire, Lane, trainings

REFERENCE = SCENARIO_REGISTRY["reference_greenhouse"]
# Two rows of six along x, on gutters 0.25 m beyond their ends, under a pair
# of wires 0.3 m either side, 3.5 m up: from x = 1.75 to 4.75 m.
ROWS = CropRows(
    origin=Point2(x=2.0, y=2.0),
    rows=2,
    positions_per_row=6,
    plant_pitch=0.5,
    row_spacing=1.6,
    support=TOMATO_GUTTER,
    wires=CropWires(height=3.5, offset=0.3),
)
FOOT_HEIGHT_M = TOMATO_GUTTER.planting_height
WIRE_M = 3.5 - FOOT_HEIGHT_M
HALF_WIDTH_M = TOMATO_GUTTER.width / 2
# The lab's first plant on day 85, its two lowest trusses cut: bare of
# fruit up to its third truss.
RIPE = lab.structure(lab.LabRun(day=85))
CUT = act(act(RIPE, HarvestTruss(truss_id="p01_t01")), HarvestTruss(truss_id="p01_t02"))
# The same rows, their wires 3 m up, and a crop worked as the reference's.
LOW_ROWS = ROWS.model_copy(update={"wires": CropWires(height=3.0, offset=0.3)})
LOWERED = CropWork(harvest_every_days=7, lower_every_days=7, head_room_m=0.3)


def _close(a: Vector3, b: Vector3) -> bool:
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) < 1e-9


def test_a_double_row_has_a_wire_either_side_of_each_row() -> None:
    fixtures = {f.fixture_id: f for f in ROWS.fixtures()}

    wires = sorted(name for name in fixtures if "_wire_" in name)
    assert wires == [f"row_{r}_wire_1_{side}" for r in (1, 2) for side in ("left", "right")]
    left, right = fixtures["row_1_wire_1_left"], fixtures["row_1_wire_1_right"]
    assert left.transform.position.y == pytest.approx(2.3)
    assert right.transform.position.y == pytest.approx(1.7)
    assert left.transform.position.z == pytest.approx(3.5)


def test_its_plants_are_trained_to_its_wires_by_turns() -> None:
    trained = trainings(ROWS, [])
    paths = [t.path for t in trained]

    assert [t.position for t in trained] == ROWS.planting_positions()
    assert all(isinstance(path, HighWire) for path in paths)
    assert [path.on_the_left for path in paths if isinstance(path, HighWire)][:6] == [
        True,
        False,
        True,
        False,
        True,
        False,
    ]
    assert [t.wire_m for t in trained] == pytest.approx([WIRE_M] * len(trained))


@pytest.mark.parametrize("index", [0, 1])
def test_a_stem_rises_from_its_foot_to_its_own_wire(index: int) -> None:
    path = trainings(ROWS, [])[index].path
    rising = path.rising(0.0)

    # Followed to the wire's height, it reaches the wire on its side.
    reach = WIRE_M / rising.z
    sideways = 0.3 if index == 0 else -0.3
    assert (rising.x * reach, rising.y * reach) == pytest.approx((0.0, sideways))


def test_the_lane_runs_round_the_gutter_from_one_edge_to_the_other() -> None:
    lane = Lane(
        start=Vector3(x=1.75, y=2.0, z=0.0),
        end=Vector3(x=4.75, y=2.0, z=0.0),
        half_width=0.15,
    )
    turn = math.pi * 0.15

    assert lane.length_m == pytest.approx(2 * 3.0 + 2 * turn)
    left_start, outward = lane.at(0.0)
    assert _close(left_start, Vector3(x=1.75, y=2.15, z=0.0))
    assert _close(outward, Vector3(x=0.0, y=1.0, z=0.0))
    # Half way round its far end, it is past the gutter's end, facing on.
    far, outward = lane.at(3.0 + turn / 2)
    assert _close(far, Vector3(x=4.9, y=2.0, z=0.0))
    assert _close(outward, Vector3(x=1.0, y=0.0, z=0.0))
    right_end, outward = lane.at(3.0 + turn)
    assert _close(right_end, Vector3(x=4.75, y=1.85, z=0.0))
    assert _close(outward, Vector3(x=0.0, y=-1.0, z=0.0))
    near, _ = lane.at(2 * 3.0 + 1.5 * turn)
    assert _close(near, Vector3(x=1.6, y=2.0, z=0.0))
    # Once round, it is back where it started.
    assert _close(lane.at(lane.length_m)[0], left_start)


def test_a_laid_stem_lies_forward_on_the_left_back_on_the_right_and_turns_the_end() -> None:
    first, second, *_, last = trainings(ROWS, [])[:6]
    lane_z = 0.0

    # The first plant, on the left wire, lays its stem forward along the
    # gutter's left edge; the second, on the right, back along its right.
    assert _close(first.path.laid(1.0), Vector3(x=1.0, y=HALF_WIDTH_M, z=lane_z))
    assert _close(second.path.laid(0.5), Vector3(x=-0.5, y=-HALF_WIDTH_M, z=lane_z))
    # The last, on the right, 0.25 m from the gutter's end: its stem lies
    # back along the right edge too, rising towards the right wire.
    assert _close(last.path.laid(0.5), Vector3(x=-0.5, y=-HALF_WIDTH_M, z=lane_z))
    # The fifth plant, on the left, 0.75 m from the end: past it, its stem
    # turns round to the right edge and rises towards the right wire.
    fifth = trainings(ROWS, [])[4]
    turn = math.pi * HALF_WIDTH_M
    beyond = fifth.path.laid(0.75 + turn + 0.5)
    assert _close(beyond, Vector3(x=0.25, y=-HALF_WIDTH_M, z=lane_z))
    rising = fifth.path.rising(0.75 + turn + 0.5)
    reach = WIRE_M / rising.z
    assert rising.y * reach == pytest.approx(-(0.3 - HALF_WIDTH_M))


def test_without_a_pair_of_wires_a_stem_is_laid_straight_along_its_row() -> None:
    single = ROWS.model_copy(update={"wires": CropWires(height=3.5), "heading": math.pi / 2})
    path = trainings(single, [])[0].path

    assert isinstance(path, AlongItsRow)
    assert _close(path.laid(1.0), Vector3(x=0.0, y=1.0, z=0.0))
    assert _close(path.rising(1.0), Vector3(x=0.0, y=0.0, z=1.0))
    assert Layout(crop_rows=single).trainings()[0].wire_m == pytest.approx(WIRE_M)


def test_the_reference_greenhouse_is_a_high_wire_double_row() -> None:
    trained = REFERENCE.layout.trainings()

    assert len(trained) == 32
    assert all(isinstance(t.path, HighWire) for t in trained)
    wires = [f for f in REFERENCE.layout.fixtures() if "_wire_" in f.fixture_id]
    assert len(wires) == 8


def test_a_lowering_round_lays_down_the_bare_stem_its_top_has_to_come_down_by() -> None:
    height = top_height_m(CUT)
    most = height - 0.1

    lowered = lowering_round(CUT, most)

    assert top_height_m(lowered) <= most
    # It lays down no more than it must: one internode fewer would not do.
    assert top_height_m(CUT, laid=lowered.laid_internodes - 1) > most
    stripped = [p.leaf.leaf_id for p in CUT.stem.phytomers[: lowered.laid_internodes]]
    removed = [e.action.leaf_id for e in lowered.history[len(CUT.history) : -1]]  # type: ignore[union-attr]
    assert (
        removed
        == [leaf for leaf in stripped if CUT.stem.phytomers[0].leaf.stage != LeafStage.REMOVED][
            : len(removed)
        ]
    )
    assert lowered.history[-1].note.startswith(f"laid {lowered.laid_internodes} internodes down")
    assert lowered.problems() == [] and lowered.problems_since(CUT) == []


def test_a_lowering_round_leaves_a_plant_under_its_mark_alone() -> None:
    assert lowering_round(CUT, top_height_m(CUT) + 0.01) == CUT


def test_a_lowering_round_never_lays_down_a_truss_still_bearing() -> None:
    # Its lowest truss still bears red fruit: nothing below it is laid down
    # past it, however far its top is over.
    lowered = lowering_round(RIPE, 0.1)
    first_truss = next(i for i, p in enumerate(RIPE.stem.phytomers) if p.truss is not None)

    assert lowered.laid_internodes <= first_truss
    assert top_height_m(lowered) > 0.1


def test_a_laid_stem_is_drawn_along_its_path_and_the_rest_rises_towards_its_wire() -> None:
    fifth = trainings(ROWS, [])[4]
    lowered = lowering_round(CUT, top_height_m(CUT, fifth.path) - 0.5, fifth.path)
    shapes = {s.shape_id: s for s in organ_geometry(lowered, path=fifth.path)}
    laid = lowered.laid_internodes
    internodes = [p.internode.internode_id for p in lowered.stem.phytomers]

    assert laid > 0
    # Each laid internode starts where the path has reached, along it.
    reached = 0.0
    for index in range(1, laid):
        reached += lowered.stem.phytomers[index - 1].internode.length_cm / 100
        start = shapes[internodes[index]].transform.position
        assert _close(start, fifth.path.laid(reached))
    # The stem rises from where its laid part ends, leaning to its wire.
    rises = shapes[internodes[laid]].transform
    assert _close(rises.position, rising_point(lowered, fifth.path))
    axis = rises.rotation.rotate(Vector3(x=0.0, y=0.0, z=1.0))
    assert _close(axis, fifth.path.rising(laid_length_m(lowered)))
    # Along the row by default, as before.
    straight = {s.shape_id: s for s in organ_geometry(lowered, path=ALONG_THE_ROW)}
    assert _close(
        straight[internodes[laid]].transform.position,
        Vector3(x=0.0, y=laid_length_m(lowered), z=0.0),
    )


class _Steady:
    """The reference environment's light on every crown, all day."""

    def __init__(self, crowns: Sequence[Crown]) -> None:
        self.crowns = list(crowns)

    def par_at(self, time_s: float) -> dict[str, float]:
        return {crown.plant_id: 500.0 for crown in self.crowns}

    def daily_light_integral(self, day: int = 0) -> dict[str, float]:
        return {crown.plant_id: 25.0 for crown in self.crowns}


def _season(work: CropWork) -> RunCrop:
    """Six plants of a double row whose wires hang 3 m up, so that the lab's
    reference air and light bring them to the wires within the season."""
    return RunCrop(
        [transplant(f"p{n}", 42) for n in range(1, 7)],
        trainings(LOW_ROWS, [])[:6],
        REFERENCE.envelope,
        air=lambda _: HouseAir(temperature_c=21.0, humidity_g_kg=8.0, co2_ppm=800.0),
        light=lambda _, crowns: _Steady(crowns),
        work=work,
        days=120,
    )


def test_a_weekly_lowering_keeps_every_top_under_its_wire_after_each_round() -> None:
    crop = _season(LOWERED)
    trained = trainings(LOW_ROWS, [])[:6]
    most = trained[0].wire_m - LOWERED.head_room_m  # type: ignore[operator]

    for day in range(7, 120, 7):
        for plant, training in zip(crop.plants_on(day), trained, strict=True):
            assert top_height_m(plant, training.path) <= most + 1e-9, (day, plant.plant_id)
    plants = crop.plants_on(119)
    assert all(plant.laid_internodes > 0 for plant in plants)
    assert all(plant.problems() == [] for plant in plants)
    # Unlowered, the same crop would stand over its wires.
    unlowered = _season(CropWork(harvest_every_days=7))
    assert max(top_height_m(p) for p in unlowered.plants_on(119)) > trained[0].wire_m  # type: ignore[operator]


def test_a_lowered_plants_crown_stands_where_its_stem_rises() -> None:
    crop = _season(LOWERED)
    plants = crop.plants_on(105)

    for crown, plant, training in zip(
        crop.crowns_on(105), plants, trainings(LOW_ROWS, []), strict=False
    ):
        rises = rising_point(plant, training.path)
        foot = training.position.point
        expected = REFERENCE.envelope.to_world(
            Vector3(x=foot.x + rises.x, y=foot.y + rises.y, z=foot.z + rises.z)
        )
        assert _close(crown.base, expected)
        assert crown.height_m == pytest.approx(stem_height_m(plant))


def test_the_timeline_lists_a_lowering_round_after_the_harvest_round() -> None:
    run = RunProcesses(
        schedule=Schedule(),
        air_step_s=None,
        plants=["p1"],
        sensors=[],
        cameras=[],
        crop_work=LOWERED,
    )

    at_midnight = [e.kind for e in events(run, 6 * DAY_S, 7 * DAY_S) if e.time_s == 7 * DAY_S]

    assert at_midnight == ["day 6", HARVEST_ROUND, LOWERING_ROUND]
