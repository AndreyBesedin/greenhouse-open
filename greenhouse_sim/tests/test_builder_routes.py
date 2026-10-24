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


@pytest.mark.parametrize(
    ("changes", "fields"),
    [
        ({"ridge_height_m": 3.0}, ["ridge_height_m"]),
        ({"length_m": 600.0}, ["length_m"]),
        ({"eave_height_m": 60.0, "ridge_height_m": 70.0}, ["eave_height_m", "ridge_height_m"]),
        ({"support_height_m": 0.1}, ["support_height_m"]),
        ({"spans": 50, "bays": 50}, ["bays"]),
        ({"rows": 1000, "plants_per_row": 1000}, ["plants_per_row"]),
        ({"row_spacing_m": 0.2}, ["row_spacing_m"]),
    ],
    ids=["ridge", "length", "heights", "support", "spans by bays", "plants", "spacing"],
)
def test_a_value_the_house_refuses_is_refused_by_the_forms_field(
    simulator: Simulator, changes: dict[str, float], fields: list[str]
) -> None:
    """The envelope and the rows check what the form's values become; a
    value they refuse is named as the form names it, as are all of them."""
    status, answered = _post(simulator, "/api/builder/basic", json.dumps(FORM | changes))

    assert status == HTTPStatus.BAD_REQUEST, answered
    assert answered["error"].startswith(f"not the first form's values: {fields[0]}: ")
    assert [problem["field"] for problem in answered["problems"]] == fields


@pytest.mark.parametrize("path", ["/api/builder/assess", "/api/builder/scene"])
def test_a_file_refused_names_every_field_at_fault(simulator: Simulator, path: str) -> None:
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))
    document = json.loads(_file(first))
    document["envelope"]["length"] = -1
    document["row_crops"][1]["crop_model"] = "tomato.simple"

    status, answered = _post(simulator, path, json.dumps(document))

    assert status == HTTPStatus.BAD_REQUEST
    assert answered["error"].endswith("(and 1 more)")
    assert [problem["field"] for problem in answered["problems"]] == [
        "envelope.length",
        "row_crops[1].crop_model",
    ]


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
    # An installation not kept as a draft names none.
    assert "draft" not in assessed


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


def test_a_scenario_planting_part_of_its_layout_is_not_copied() -> None:
    """A copy would plant every position of each row: one plant in a layout
    of two rows of sixteen would run as thirty-two."""
    one_plant = SCENARIO_REGISTRY["climate_box"].model_copy(
        update={"greenhouse_id": "one_plant", "rows": 1, "columns": 1}
    )
    with Simulator() as fresh:
        fresh.catalogue.register(one_plant)

        answer = respond(fresh, "GET", "/api/scenarios/one_plant/installation")

    answered: Any = answer.body
    assert answer.status == HTTPStatus.BAD_REQUEST
    assert "1 rows of 1 plants does not fill its layout's 2 rows of 16" in answered["error"]


@pytest.mark.parametrize(
    ("path", "body", "said"),
    [
        ("/api/builder/basic", json.dumps(FORM | {"plants_per_row": 10**309}), "plants_per_row"),
        ("/api/builder/basic", json.dumps(FORM | {"rows": 10**309}), "rows"),
        # Whether Python reads JSON nested so deep at all depends on its
        # stack, which differs from one platform to another: refused either
        # way, as too deep or as no form or file.
        ("/api/builder/basic", "[" * 100_000 + "]" * 100_000, ""),
        ("/api/builder/assess", "[" * 100_000 + "]" * 100_000, ""),
        ("/api/builder/scene", "[" * 100_000 + "]" * 100_000, ""),
        ("/api/builder/basic", json.dumps(FORM).replace("12.0", "1e999", 1), "too large a number"),
    ],
    ids=["huge plants", "huge rows", "nested basic", "nested assess", "nested scene", "1e999"],
)
def test_what_no_greenhouse_has_is_refused_not_failed_on(
    simulator: Simulator, path: str, body: str, said: str
) -> None:
    status, answered = _post(simulator, path, body)

    assert (status, said in answered["error"]) == (HTTPStatus.BAD_REQUEST, True), answered


def test_an_installations_file_with_an_infinite_number_is_refused(simulator: Simulator) -> None:
    """Python reads `1e999` as infinity; no greenhouse's number is."""
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))
    file = _file(first).replace('"length": 12.0', '"length": 1e999', 1)
    assert "1e999" in file

    for path in ("/api/builder/assess", "/api/builder/scene"):
        status, answered = _post(simulator, path, file)
        assert (status, "too large a number" in answered["error"]) == (
            HTTPStatus.BAD_REQUEST,
            True,
        ), answered


# A vent midway up a slope of the form's house, 1.58 m from eave to ridge.
VENT: dict[str, Any] = {
    "opening_id": "vent",
    "kind": "roof_vent",
    "surface_id": "roof_1_right",
    "centre": {"x": 0.0, "y": 0.0},
    "width": 1.0,
    "height": 0.6,
}


def _edit(simulator: Simulator, answered: dict[str, Any], edit: dict[str, Any]) -> tuple[int, Any]:
    body = {"file": json.loads(_file(answered)), "edit": edit}
    return _post(simulator, "/api/builder/edit", json.dumps(body))


def test_an_edit_of_many_items_answers_the_installation_it_makes_assessed(
    simulator: Simulator,
) -> None:
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))
    spread = {
        "edit": "spread_openings",
        "opening": VENT,
        "surfaces": ["roof_1_right", "roof_2_left"],
        "count": 4,
    }

    status, edited = _edit(simulator, first, spread)

    assert status == HTTPStatus.OK
    openings = edited["installation"]["envelope"]["openings"]
    assert [(o["opening_id"], o["surface_id"]) for o in openings][::4] == [
        ("vent_1", "roof_1_right"),
        ("vent_5", "roof_2_left"),
    ]
    assert len(openings) == 8
    assert "no_vents" not in {finding["code"] for finding in edited["findings"]}
    # What it answers is a file an editor sends back, for the next edit.
    removed = {"edit": "remove_items", "items": ["vent_1", "vent_5"]}
    status, fewer = _edit(simulator, edited, removed)
    assert (status, len(fewer["installation"]["envelope"]["openings"])) == (HTTPStatus.OK, 6)


def test_walkways_and_zones_are_placed_as_equipment_is(simulator: Simulator) -> None:
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))
    walkway = {
        "primitive": "walkway",
        "fixture_id": "path",
        "start": {"x": 2.0, "y": 0.3},
        "end": {"x": 2.0, "y": 5.7},
        "width": 0.8,
    }
    zone = {
        "zone_id": "service",
        "kind": "service",
        "area": {"start": {"x": 11.0, "y": 0.5}, "end": {"x": 11.0, "y": 1.5}, "width": 0.8},
        "height": 2.0,
    }
    step = {"x": 4.0, "y": 0.0, "z": 0.0}

    status, paths = _edit(
        simulator, first, {"edit": "place_items", "item": walkway, "count": 2, "step": step}
    )
    status, edited = _edit(simulator, paths, {"edit": "place_items", "item": zone})

    assert status == HTTPStatus.OK, edited
    layout = edited["installation"]["layout"]
    assert [p["fixture_id"] for p in layout["placed"]] == ["path_1", "path_2"]
    assert [z["zone_id"] for z in layout["zones"]] == ["service_1"]


@pytest.mark.parametrize(
    ("edit", "said"),
    [
        ({"edit": "remove_items", "items": ["heater_9"]}, "the edit is refused: no item heater_9"),
        (
            {
                "edit": "place_openings",
                "opening": VENT | {"centre": {"x": 5.8, "y": 0.0}},
                "surfaces": ["roof_1_right"],
            },
            "vent_1 does not fit on roof_1_right",
        ),
        (
            {"edit": "space_items", "items": ["a", "b"], "axis": "w"},
            "not an edit: edit.space_items.axis",
        ),
        ({"edit": "paint", "items": []}, "not an edit: edit"),
    ],
)
def test_an_edit_refused_or_no_edit_at_all_says_why(
    simulator: Simulator, edit: dict[str, Any], said: str
) -> None:
    status, first = _post(simulator, "/api/builder/basic", json.dumps(FORM))

    status, answer = _edit(simulator, first, edit)

    assert (status, said in answer["error"]) == (HTTPStatus.BAD_REQUEST, True), answer


def test_an_edit_on_a_file_that_is_no_installation_is_refused_by_its_field(
    simulator: Simulator,
) -> None:
    body = {
        "file": {"schema_version": SCHEMA_VERSION, "name": "No house"},
        "edit": {"edit": "remove_items", "items": ["x"]},
    }

    status, answer = _post(simulator, "/api/builder/edit", json.dumps(body))

    assert status == HTTPStatus.BAD_REQUEST
    assert {problem["field"] for problem in answer["problems"]} >= {"installation_id", "envelope"}
