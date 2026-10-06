"""The scene contract as published for the viewer, in step with the types.

`greenhouse_sim/scene/snapshot.schema.json` is what the viewer generates its
types from and validates scenes against, `web/public/scenes/example.json` is a
deterministic scene the viewer can draw without the API, and
`web/public/scenes/qa-greenhouse.json` is the canonical greenhouse its
screenshot tests draw (P01.7), `web/public/scenes/qa-fixtures.json` is its
gallery of fixture primitives (P02.1), and `web/public/scenes/qa-layout.json`
is the canonical layout its layout views draw (P02.4). All five are
generated here, from `greenhouse_sim/`:

    python tests/test_scene_schema.py --update

These tests fail if any drifts from what the simulator produces now. They
compare parsed JSON, so formatting does not count.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import (
    JSON_SCHEMA_DIALECT,
    greenhouse_scene,
    scene_snapshot,
    snapshot_json_schema,
)
from greenhouse_sim.world.envelope import Envelope, Opening, OpeningKind
from greenhouse_sim.world.fixtures import (
    BoxPrimitive,
    CylinderPrimitive,
    Material,
    PipePrimitive,
    PipeRunPrimitive,
    RailPrimitive,
    TrayPrimitive,
    WalkwayPrimitive,
)
from greenhouse_sim.world.geometry import Point2, Transform, Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import PIPE_RAIL, TOMATO_GUTTER, CropRows, CropWires
from greenhouse_sim.world.zones import Strip, Zone, ZoneKind

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "greenhouse_sim" / "scene" / "snapshot.schema.json"
EXAMPLE_FILE = ROOT / "web" / "public" / "scenes" / "example.json"
QA_GREENHOUSE_FILE = ROOT / "web" / "public" / "scenes" / "qa-greenhouse.json"
QA_FIXTURES_FILE = ROOT / "web" / "public" / "scenes" / "qa-fixtures.json"
QA_LAYOUT_FILE = ROOT / "web" / "public" / "scenes" / "qa-layout.json"
# The canonical greenhouse for the viewer's screenshot tests: three 3.2 m
# spans and four 4 m bays, its eaves at 4 m and ridges at 4.65 m, with a roof
# vent half open, a closed side vent and a door half open.
QA_ENVELOPE = Envelope(
    length=16.0,
    width=9.6,
    eave_height=4.0,
    ridge_height=4.65,
    spans=3,
    bays=4,
    openings=[
        Opening(
            opening_id="roof_vent_1",
            kind=OpeningKind.ROOF_VENT,
            surface_id="roof_2_right",
            centre=Point2(x=0.0, y=0.5),
            width=3.0,
            height=0.6,
            opening=0.5,
        ),
        Opening(
            opening_id="side_vent_1",
            kind=OpeningKind.SIDE_VENT,
            surface_id="side_wall_left",
            centre=Point2(x=0.0, y=1.2),
            width=4.0,
            height=0.6,
        ),
        Opening(
            opening_id="door_1",
            kind=OpeningKind.DOOR,
            surface_id="end_wall_front",
            centre=Point2(x=1.6, y=1.05),
            width=1.2,
            height=2.1,
            opening=0.5,
        ),
    ],
)
# The gallery of fixture primitives: one of each, side by side along an 8 by
# 4.8 m greenhouse, each running across it. The greenhouse is centred on the
# world's origin, where the viewer's camera presets look.
QA_FIXTURES_ENVELOPE = Envelope(
    length=8.0,
    width=4.8,
    eave_height=3.0,
    ridge_height=3.65,
    bays=2,
    origin=Transform(position=Vector3(x=-4.0, y=-2.4, z=0.0)),
)
QA_FIXTURES_LAYOUT = Layout(
    placed=[
        BoxPrimitive(
            fixture_id="cabinet",
            base=Vector3(x=1.2, y=2.4, z=0.0),
            size_x=0.6,
            size_y=1.2,
            size_z=1.8,
        ),
        CylinderPrimitive(
            fixture_id="tank",
            base=Vector3(x=2.4, y=2.4, z=0.0),
            radius=0.5,
            height=1.5,
            material=Material.PLASTIC,
        ),
        PipePrimitive(
            fixture_id="heating_pipe",
            start=Vector3(x=3.4, y=0.6, z=0.3),
            end=Vector3(x=3.4, y=4.2, z=0.9),
            radius=0.0255,
        ),
        RailPrimitive(
            fixture_id="pipe_rail",
            start=Vector3(x=4.5, y=0.6, z=0.1),
            end=Vector3(x=4.5, y=4.2, z=0.1),
            gauge=0.55,
            tube_radius=0.0255,
        ),
        TrayPrimitive(
            fixture_id="crop_gutter",
            start=Vector3(x=5.6, y=0.6, z=0.0),
            end=Vector3(x=5.6, y=4.2, z=0.0),
            width=0.3,
            depth=0.12,
            material=Material.PLASTIC,
        ),
        WalkwayPrimitive(
            fixture_id="walkway",
            start=Point2(x=6.8, y=0.3),
            end=Point2(x=6.8, y=4.5),
            width=1.2,
        ),
    ]
)
# The canonical layout, in the QA greenhouse: five rows of tomato gutters
# along its length under crop wires, with pipe rails between them, split by a
# central aisle; aisles across the front, past the door, and along the right
# side wall; heating pipes along both side walls; a service zone at the back;
# and a keep-out volume around an electrical cabinet, which cuts the last row
# short.
QA_LAYOUT = Layout(
    crop_rows=CropRows(
        origin=Point2(x=1.75, y=2.0),
        rows=5,
        positions_per_row=26,
        plant_pitch=0.5,
        row_spacing=1.6,
        support=TOMATO_GUTTER,
        rails=PIPE_RAIL,
        wires=CropWires(height=3.5),
    ),
    placed=[
        WalkwayPrimitive(
            fixture_id="front_aisle",
            start=Point2(x=0.7, y=0.2),
            end=Point2(x=0.7, y=9.4),
            width=1.2,
        ),
        WalkwayPrimitive(
            fixture_id="central_aisle",
            start=Point2(x=8.0, y=1.2),
            end=Point2(x=8.0, y=9.4),
            width=1.2,
        ),
        WalkwayPrimitive(
            fixture_id="side_aisle_right",
            start=Point2(x=1.3, y=0.7),
            end=Point2(x=15.8, y=0.7),
            width=0.8,
        ),
        *(
            PipeRunPrimitive(
                fixture_id=f"heating_pipes_{side}",
                start=Vector3(x=1.3, y=y, z=0.3),
                end=Vector3(x=15.8, y=y, z=0.3),
                radius=0.0255,
                count=4,
                step=Vector3(x=0.0, y=0.0, z=0.15),
            )
            for side, y in (("right", 0.15), ("left", 9.45))
        ),
        BoxPrimitive(
            fixture_id="electrical_cabinet",
            base=Vector3(x=15.2, y=8.9, z=0.0),
            size_x=0.8,
            size_y=0.6,
            size_z=2.0,
        ),
    ],
    zones=[
        Zone(
            zone_id="service_zone_back",
            kind=ZoneKind.SERVICE,
            area=Strip(start=Point2(x=15.35, y=1.2), end=Point2(x=15.35, y=7.8), width=1.1),
            height=2.0,
        ),
        Zone(
            zone_id="keep_out_cabinet",
            kind=ZoneKind.KEEP_OUT,
            area=Strip(start=Point2(x=13.4, y=8.65), end=Point2(x=15.9, y=8.65), width=1.5),
            height=2.4,
        ),
    ],
)
# Long enough in gh_demo for the plants to differ in height.
EXAMPLE_DAYS = 9


def _example_scene() -> object:
    config = SCENARIO_REGISTRY["gh_demo"]
    engine = SimulationEngine(config)
    plant_ids = [f"gh_demo_plant_{i:03d}" for i in range(1, config.rows * config.columns + 1)]
    world = engine.initialize(plant_ids, greenhouse_id="gh_demo")
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    for day in range(1, EXAMPLE_DAYS + 1):
        timestamp = start + timedelta(days=day - 1)
        world = engine.advance(world, day=day, timestamp=timestamp, simulation_id="example").world
    return scene_snapshot(world, config).model_dump(mode="json")


def test_the_published_schema_matches_the_snapshot_types() -> None:
    assert json.loads(SCHEMA_FILE.read_text()) == snapshot_json_schema()


def test_the_published_schema_is_plain_json_schema() -> None:
    """No OpenAPI keywords, so a standard validator accepts it in strict mode."""
    text = SCHEMA_FILE.read_text()

    assert json.loads(text)["$schema"] == JSON_SCHEMA_DIALECT
    assert '"discriminator"' not in text


def test_the_example_scene_is_what_the_simulator_draws() -> None:
    assert json.loads(EXAMPLE_FILE.read_text()) == _example_scene()


def _qa_greenhouse() -> object:
    return greenhouse_scene("qa_greenhouse", QA_ENVELOPE).model_dump(mode="json")


def test_the_qa_greenhouse_is_what_the_simulator_draws() -> None:
    assert json.loads(QA_GREENHOUSE_FILE.read_text()) == _qa_greenhouse()


def _qa_fixtures() -> object:
    scene = greenhouse_scene("qa_fixtures", QA_FIXTURES_ENVELOPE, layout=QA_FIXTURES_LAYOUT)
    return scene.model_dump(mode="json")


def test_the_qa_fixture_gallery_is_what_the_simulator_draws() -> None:
    assert json.loads(QA_FIXTURES_FILE.read_text()) == _qa_fixtures()


def _qa_layout() -> object:
    return greenhouse_scene("qa_layout", QA_ENVELOPE, layout=QA_LAYOUT).model_dump(mode="json")


def test_the_qa_layout_is_what_the_simulator_draws() -> None:
    assert json.loads(QA_LAYOUT_FILE.read_text()) == _qa_layout()


def test_the_example_scene_holds_differently_sized_and_placed_plants() -> None:
    entities = json.loads(EXAMPLE_FILE.read_text())["entities"]
    plants = [entity for entity in entities if entity["kind"] == "PLANT"]
    heights = {plant["shape"]["height"] for plant in plants}
    positions = {tuple(plant["transform"]["position"].values()) for plant in plants}

    assert len(plants) > 1
    assert len(heights) == len(plants)
    assert len(positions) == len(plants)


def _update() -> None:
    SCHEMA_FILE.write_text(json.dumps(snapshot_json_schema(), indent=2) + "\n")
    EXAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_FILE.write_text(json.dumps(_example_scene(), indent=2) + "\n")
    QA_GREENHOUSE_FILE.write_text(json.dumps(_qa_greenhouse(), indent=2) + "\n")
    QA_FIXTURES_FILE.write_text(json.dumps(_qa_fixtures(), indent=2) + "\n")
    QA_LAYOUT_FILE.write_text(json.dumps(_qa_layout(), indent=2) + "\n")


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_scene_schema.py --update")
    _update()
    written = (SCHEMA_FILE, EXAMPLE_FILE, QA_GREENHOUSE_FILE, QA_FIXTURES_FILE, QA_LAYOUT_FILE)
    print("wrote", ", ".join(str(path) for path in written))
