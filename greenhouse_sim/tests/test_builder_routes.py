"""What the setup builder asks of the simulator besides its drafts (P12.2):
a first draft from its first form, an edit assessed before it is saved,
and the scene of a house to preview, each answered from an installation's
file and with one an editor can send back."""

import json
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.builder.portable import export_installation
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.scenarios.manifest_files import MANIFESTS_DIR, SCHEMA_VERSION, manifest_ids
from greenhouse_sim.scene.snapshot import SceneEntityKind
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.world.envelope import Envelope

FORM: dict[str, Any] = {
    "installation_id": "my_greenhouse",
    "name": "Test house",
    "length_m": 12.0,
    "width_m": 6.0,
    "eave_height_m": 4.0,
    "ridge_height_m": 4.5,
    "spans": 2,
    "bays": 3,
    "rows": 2,
    "plants_per_row": 6,
    "plant_pitch_m": 0.75,
    "row_spacing_m": 1.6,
    "support_height_m": 0.5,
    "crop_model": "simple",
    "variety": "cherry_tomato",
}


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    with Simulator() as made:
        yield made


def _post(simulator: Simulator, path: str, body: str) -> tuple[int, Any]:
    answer = respond(simulator, "POST", path, body.encode())
    return answer.status, answer.body


def _file(answered: dict[str, Any]) -> str:
    """The installation an answer holds, as its file: what an editor sends
    back."""
    return json.dumps({"schema_version": answered["schema_version"], **answered["installation"]})


def test_the_first_form_makes_a_draft_assessed(simulator: Simulator) -> None:
    status, answered = _post(simulator, "/api/builder/basic", json.dumps(FORM))

    assert status == HTTPStatus.OK
    assert answered["schema_version"] == SCHEMA_VERSION
    installation = Installation.model_validate(answered["installation"])
    assert installation.layout.crop_rows is not None
    assert installation.layout.crop_rows.positions_per_row == FORM["plants_per_row"]
    assert [crop.row for crop in installation.row_crops] == [1, 2]
    assert {found["code"] for found in answered["findings"]} == {
        "no_door",
        "no_vents",
        "no_heating",
        "no_fans",
    }


@pytest.mark.parametrize(
    ("form", "said"),
    [
        (FORM | {"length_m": -1}, "length_m: Input should be greater than 0"),
        (FORM | {"rooms": 3}, "rooms"),
        ({key: value for key, value in FORM.items() if key != "rows"}, "rows: Field required"),
        (FORM | {"ridge_height_m": 3.0}, "ridge"),
    ],
)
def test_form_values_no_greenhouse_can_have_are_refused_by_field(
    simulator: Simulator, form: dict[str, Any], said: str
) -> None:
    status, answered = _post(simulator, "/api/builder/basic", json.dumps(form))

    assert (status, said in answered["error"]) == (HTTPStatus.BAD_REQUEST, True), answered


def test_an_edit_is_assessed_as_it_stands_and_sent_back_as_it_came(simulator: Simulator) -> None:
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))
    edited = json.loads(_file(first))
    edited["row_crops"] = edited["row_crops"][:1]

    status, assessed = _post(simulator, "/api/builder/assess", json.dumps(edited))

    assert status == HTTPStatus.OK
    (unassigned,) = [f for f in assessed["findings"] if f["code"] == "unassigned_rows"]
    assert unassigned["rows"] == [2]
    # What it answers is what it was sent, read.
    assert json.loads(_file(assessed)) == edited


def test_a_house_is_previewed_as_the_simulator_draws_it(simulator: Simulator) -> None:
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))
    house = Installation.model_validate(first["installation"])

    status, scene = _post(simulator, "/api/builder/scene", _file(first))

    assert status == HTTPStatus.OK
    assert scene["greenhouse_id"] == "my_greenhouse"
    kinds = {entity["kind"] for entity in scene["entities"]}
    assert {SceneEntityKind.WALL.value, SceneEntityKind.ROOF.value} <= kinds
    positions = [e for e in scene["entities"] if e["kind"] == SceneEntityKind.PLANTING_POSITION]
    assert len(positions) == len(house.layout.planting_positions()) == 12
    # No crop yet: a house to preview, not a run.
    assert SceneEntityKind.PLANT.value not in kinds


@pytest.mark.parametrize("path", ["/api/builder/assess", "/api/builder/scene"])
@pytest.mark.parametrize(
    ("body", "said"),
    [
        ("{not json", "not JSON"),
        (json.dumps({"schema_version": SCHEMA_VERSION}), "installation_id"),
        (json.dumps({"schema_version": 99}), "format 99"),
    ],
)
def test_what_is_no_installations_file_is_refused(
    simulator: Simulator, path: str, body: str, said: str
) -> None:
    status, answered = _post(simulator, path, body)

    assert (status, said in answered["error"]) == (HTTPStatus.BAD_REQUEST, True), answered


def test_a_file_exported_reads_back_through_the_builder(simulator: Simulator) -> None:
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))
    exported = export_installation(Installation.model_validate(first["installation"]))

    status, assessed = _post(simulator, "/api/builder/assess", exported)

    assert (status, assessed["installation"]) == (HTTPStatus.OK, first["installation"])


@pytest.mark.parametrize("scenario_id", manifest_ids())
def test_a_scenarios_house_is_its_manifests_installation(
    simulator: Simulator, scenario_id: str
) -> None:
    """For the builder to copy, as the manifest holds it, its layout written
    out; and assessed."""
    held = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())["installation"]

    answer = respond(simulator, "GET", f"/api/scenarios/{scenario_id}/installation")

    assert answer.status == HTTPStatus.OK
    answered: Any = answer.body
    installation = answered["installation"]
    for part in ("installation_id", "name", "row_crops"):
        assert installation[part] == held[part]
    # Written sparsely in the manifest, as the model reads it here.
    assert installation["envelope"] == Envelope.model_validate(held["envelope"]).model_dump(
        mode="json"
    )
    assert installation["layout"] == SCENARIO_REGISTRY[scenario_id].layout.model_dump(mode="json")
    assert all(found["severity"] == "warning" for found in answered["findings"])


def test_no_scenario_has_no_house(simulator: Simulator) -> None:
    answer = respond(simulator, "GET", "/api/scenarios/nowhere/installation")

    assert answer.status == HTTPStatus.NOT_FOUND
