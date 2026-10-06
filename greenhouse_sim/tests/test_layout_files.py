"""Scenario layouts as declarative files: each scenario reads its layout from
one, other layouts can be shown in its place, and a layout survives being
written out and read back, identifiers and all.

`greenhouse_sim/scenarios/layout.schema.json` is the schema the files name,
generated here, from `greenhouse_sim/`:

    python tests/test_layout_files.py --update
"""

import json
import sys
from http import HTTPStatus

import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import (
    DEFAULT_LAYOUT,
    LAYOUT_SCHEMA_FILE,
    LAYOUTS_DIR,
    layout_document,
    layout_json_schema,
    layout_names,
    load_layout,
)
from greenhouse_sim.scene.snapshot import SceneEntityKind, SceneSnapshot
from greenhouse_sim.world.layout import Layout

ALL_LAYOUTS = [
    (scenario_id, name) for scenario_id in SCENARIO_REGISTRY for name in layout_names(scenario_id)
]


def test_the_published_layout_schema_matches_the_layout() -> None:
    assert json.loads(LAYOUT_SCHEMA_FILE.read_text()) == layout_json_schema()


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_REGISTRY))
def test_each_scenario_is_laid_out_by_its_default_file(scenario_id: str) -> None:
    assert layout_names(scenario_id)[0] == DEFAULT_LAYOUT
    assert SCENARIO_REGISTRY[scenario_id].layout == load_layout(scenario_id)


@pytest.mark.parametrize(("scenario_id", "name"), ALL_LAYOUTS)
def test_every_layout_file_fits_its_scenario(scenario_id: str, name: str) -> None:
    config = SCENARIO_REGISTRY[scenario_id]

    config.model_validate(config.model_dump() | {"layout": load_layout(scenario_id, name)})


@pytest.mark.parametrize(("scenario_id", "name"), ALL_LAYOUTS)
def test_a_layout_file_is_exactly_what_its_layout_writes(scenario_id: str, name: str) -> None:
    """Written out and read back, a layout is the same, and so are its fixtures
    and planting positions, identifiers and all."""
    layout = load_layout(scenario_id, name)
    text = (LAYOUTS_DIR / scenario_id / f"{name}.json").read_text()
    document = layout_document(layout)
    again = Layout.model_validate({k: v for k, v in document.items() if k != "$schema"})

    assert json.loads(text) == document
    assert again == layout
    assert again.fixtures() == layout.fixtures()
    assert again.planting_positions() == layout.planting_positions()


def test_a_layout_name_cannot_reach_outside_its_scenario() -> None:
    for name in ("../gh_002/default", "DEFAULT", "nothing", ""):
        with pytest.raises(KeyError):
            load_layout("gh_001", name)


def test_a_layout_with_a_field_it_does_not_have_is_refused() -> None:
    document = layout_document(load_layout("gh_001"))
    document["crop_row"] = document.pop("crop_rows")
    document.pop("$schema")

    with pytest.raises(ValidationError, match="crop_row"):
        Layout.model_validate(document)


def test_gh_001s_bench_layout_carries_the_same_rows_on_benches() -> None:
    default, benches = load_layout("gh_001"), load_layout("gh_001", "benches")
    kinds = {fixture.kind.value for fixture in benches.fixtures()}

    assert "bench" in kinds and "crop_gutter" not in kinds
    assert [p.position_id for p in benches.planting_positions()] == [
        p.position_id for p in default.planting_positions()
    ]
    assert {p.point.z for p in benches.planting_positions()} == {0.8}


def test_the_api_shows_a_scenario_with_another_of_its_layouts() -> None:
    response = respond("GET", "/api/scenarios/gh_001/scene?layout=benches")
    snapshot = SceneSnapshot.model_validate(response.body)
    kinds = {entity.kind for entity in snapshot.entities}

    assert response.status == HTTPStatus.OK
    assert SceneEntityKind.BENCH in kinds
    assert SceneEntityKind.CROP_GUTTER not in kinds


def test_the_api_writes_a_scenarios_layout_as_its_file_holds_it() -> None:
    response = respond("GET", "/api/scenarios/gh_001/layout?layout=benches")

    assert response.status == HTTPStatus.OK
    assert response.body == json.loads((LAYOUTS_DIR / "gh_001" / "benches.json").read_text())


@pytest.mark.parametrize(
    ("path", "status", "reason"),
    [
        ("/api/scenarios/gh_001/scene?layout=hydroponic", HTTPStatus.NOT_FOUND, "no layout"),
        ("/api/scenarios/gh_001/layout?layout=..%2Fgh_002", HTTPStatus.NOT_FOUND, "no layout"),
        ("/api/scenarios/gh_002/scene?layout=benches", HTTPStatus.NOT_FOUND, "no layout"),
        # Shrunk, the greenhouse no longer holds its layout.
        (
            "/api/scenarios/gh_001/scene?envelope=length:5",
            HTTPStatus.BAD_REQUEST,
            "outside the greenhouse",
        ),
        (
            "/api/scenarios/gh_001/scene?layout=benches&envelope=length:7",
            HTTPStatus.BAD_REQUEST,
            "outside the greenhouse",
        ),
    ],
)
def test_the_api_refuses_a_layout_it_cannot_show(
    path: str, status: HTTPStatus, reason: str
) -> None:
    response = respond("GET", path)

    assert response.status == status
    assert isinstance(response.body, dict)
    assert reason in str(response.body["error"])


def _update() -> None:
    LAYOUT_SCHEMA_FILE.write_text(json.dumps(layout_json_schema(), indent=2) + "\n")


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_layout_files.py --update")
    _update()
    print(f"wrote {LAYOUT_SCHEMA_FILE}")
