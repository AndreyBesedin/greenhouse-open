"""The scene contract as published for the viewer, in step with the types.

`greenhouse_sim/scene/snapshot.schema.json` is what the viewer generates its
types from and validates scenes against, and `web/public/scenes/example.json`
is a deterministic scene the viewer can draw without the API. Both are
generated here, from `greenhouse_sim/`:

    python tests/test_scene_schema.py --update

These tests fail if either drifts from what the simulator produces now. They
compare parsed JSON, so formatting does not count.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import JSON_SCHEMA_DIALECT, scene_snapshot, snapshot_json_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "greenhouse_sim" / "scene" / "snapshot.schema.json"
EXAMPLE_FILE = ROOT / "web" / "public" / "scenes" / "example.json"
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


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_scene_schema.py --update")
    _update()
    print(f"wrote {SCHEMA_FILE} and {EXAMPLE_FILE}")
