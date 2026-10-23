"""The installations' drafts through the API (P12.1, decisions 0050 and
0051): saved, reopened, reverted and deleted, a change on a stale revision
refused as a conflict, and a draft without errors run as a scenario of its
own, registered with the simulator and drawn as any scenario is."""

import argparse
import json
import sqlite3
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

from greenhouse_sim.api import server
from greenhouse_sim.api.routes import respond
from greenhouse_sim.builder import portable
from greenhouse_sim.builder.basic import BasicSetup, basic_installation
from greenhouse_sim.builder.batch import assign_crop_to_rows
from greenhouse_sim.builder.drafts import DraftStore
from greenhouse_sim.builder.portable import export_installation
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.services.drafts import MOST_DAYS
from greenhouse_sim.services.simulator import Simulator

DRAFT = "my_greenhouse"
A_WEEK = {"start_date": "2026-04-01", "duration_days": 7}


def _house(name: str = "Test house", crop_model: CropModel = CropModel.SIMPLE) -> Installation:
    return basic_installation(
        BasicSetup(
            installation_id=DRAFT,
            name=name,
            length_m=12.0,
            width_m=6.0,
            eave_height_m=4.0,
            ridge_height_m=4.5,
            rows=2,
            plants_per_row=6,
            plant_pitch_m=0.75,
            row_spacing_m=1.6,
            support_height_m=0.5,
            crop_model=crop_model,
            variety="cherry_tomato",
        )
    )


@pytest.fixture
def simulator(tmp_path: Path) -> Iterator[Simulator]:
    with Simulator(drafts=DraftStore(tmp_path / "drafts.sqlite3")) as made:
        yield made


def _ask(simulator: Simulator, method: str, path: str, body: bytes = b"") -> tuple[int, Any]:
    answer = respond(simulator, method, path, body)
    return answer.status, answer.body


def _save(simulator: Simulator, house: Installation, on: int | None = None) -> tuple[int, Any]:
    query = "" if on is None else f"?on={on}"
    return _ask(
        simulator,
        "POST",
        f"/api/drafts/{house.installation_id}/save{query}",
        export_installation(house).encode(),
    )


def test_a_draft_is_saved_reopened_and_listed_revision_by_revision(simulator: Simulator) -> None:
    assert _ask(simulator, "GET", "/api/drafts") == (HTTPStatus.OK, [])

    status, first = _save(simulator, _house())
    # The builder's answer about an installation, naming the draft and its
    # revision.
    assert (status, first["draft"]["draft_id"], first["draft"]["revision"]) == (
        HTTPStatus.OK,
        DRAFT,
        1,
    )
    # What it lacks, as warnings: it can run.
    assert {found["code"] for found in first["findings"]} == {
        "no_door",
        "no_vents",
        "no_heating",
        "no_fans",
    }
    status, second = _save(simulator, _house(name="Renamed"), on=1)
    assert (status, second["draft"]["revision"]) == (HTTPStatus.OK, 2)

    status, listed = _ask(simulator, "GET", "/api/drafts")
    assert [(each["draft_id"], each["name"], each["revision"]) for each in listed] == [
        (DRAFT, "Renamed", 2)
    ]
    status, earlier = _ask(simulator, "GET", f"/api/drafts/{DRAFT}?revision=1")
    assert (status, earlier["installation"]["name"]) == (HTTPStatus.OK, "Test house")
    status, kept = _ask(simulator, "GET", f"/api/drafts/{DRAFT}/revisions")
    assert [each["revision"] for each in kept] == [1, 2]


def test_a_change_on_a_stale_revision_is_a_conflict(simulator: Simulator) -> None:
    _save(simulator, _house())
    _save(simulator, _house(name="Saved elsewhere"), on=1)

    for status, body in (
        _save(simulator, _house(name="Saved here"), on=1),
        _save(simulator, _house(name="A new one")),
        _ask(simulator, "POST", f"/api/drafts/{DRAFT}/revert?revision=1&on=1"),
        _ask(simulator, "POST", f"/api/drafts/{DRAFT}/delete?on=1"),
    ):
        assert status == HTTPStatus.CONFLICT, body
    status, latest = _ask(simulator, "GET", f"/api/drafts/{DRAFT}")
    assert latest["installation"]["name"] == "Saved elsewhere"


def test_a_draft_is_reverted_and_deleted(simulator: Simulator) -> None:
    _save(simulator, _house())
    _save(simulator, _house(name="Changed"), on=1)

    status, reverted = _ask(simulator, "POST", f"/api/drafts/{DRAFT}/revert?revision=1&on=2")
    assert (status, reverted["draft"]["revision"], reverted["installation"]["name"]) == (
        HTTPStatus.OK,
        3,
        "Test house",
    )
    assert _ask(simulator, "POST", f"/api/drafts/{DRAFT}/delete?on=3") == (
        HTTPStatus.OK,
        {"deleted": DRAFT},
    )
    assert _ask(simulator, "GET", f"/api/drafts/{DRAFT}")[0] == HTTPStatus.NOT_FOUND


def test_a_file_saved_with_faults_is_refused_by_every_field_at_fault(
    simulator: Simulator,
) -> None:
    document = json.loads(export_installation(_house()))
    document["envelope"]["length"] = -1
    document["row_crops"][1]["crop_model"] = "tomato.simple"

    status, answered = _ask(
        simulator, "POST", f"/api/drafts/{DRAFT}/save", json.dumps(document).encode()
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert [problem["field"] for problem in answered["problems"]] == [
        "envelope.length",
        "row_crops[1].crop_model",
    ]


@pytest.mark.parametrize(
    ("method", "path", "body", "status", "said"),
    [
        ("POST", f"/api/drafts/{DRAFT}/save", b"\xff\xfe", HTTPStatus.BAD_REQUEST, "UTF-8"),
        ("POST", f"/api/drafts/{DRAFT}/save", b"{}", HTTPStatus.BAD_REQUEST, "schema_version"),
        ("POST", f"/api/drafts/{DRAFT}/save?on=0", None, HTTPStatus.BAD_REQUEST, "not '0'"),
        ("POST", f"/api/drafts/{DRAFT}/save?on=x", None, HTTPStatus.BAD_REQUEST, "not 'x'"),
        ("POST", "/api/drafts/elsewhere/save", None, HTTPStatus.BAD_REQUEST, "not the draft"),
        ("POST", f"/api/drafts/{DRAFT}/revert?on=1", b"", HTTPStatus.BAD_REQUEST, "as revision"),
        ("POST", f"/api/drafts/{DRAFT}/delete", b"", HTTPStatus.BAD_REQUEST, "as on"),
        ("GET", "/api/drafts/elsewhere", b"", HTTPStatus.NOT_FOUND, "no draft 'elsewhere'"),
        ("GET", "/api/drafts/elsewhere/revisions", b"", HTTPStatus.NOT_FOUND, "no draft"),
        ("POST", "/api/drafts/elsewhere/run", b"{}", HTTPStatus.NOT_FOUND, "no draft"),
    ],
)
def test_what_is_not_a_drafts_request_is_refused(
    simulator: Simulator, *, method: str, path: str, body: bytes | None, status: int, said: str
) -> None:
    answered, answer = _ask(
        simulator, method, path, export_installation(_house()).encode() if body is None else body
    )

    assert (answered, said in answer["error"]) == (status, True), answer


def test_a_simulator_without_a_store_keeps_no_drafts() -> None:
    with Simulator() as simulator:
        status, answer = _ask(simulator, "GET", "/api/drafts")

    assert status == HTTPStatus.NOT_FOUND
    assert "keeps no drafts" in answer["error"]


def test_a_draft_without_errors_runs_as_a_scenario_of_its_own(simulator: Simulator) -> None:
    """Grown organ by organ, so that its crop is drawn too."""
    _save(simulator, _house(crop_model=CropModel.ORGAN))

    status, registered = _ask(
        simulator, "POST", f"/api/drafts/{DRAFT}/run", json.dumps(A_WEEK).encode()
    )

    assert status == HTTPStatus.OK, registered
    assert (registered["id"], registered["name"], registered["plants"]) == (
        "my_greenhouse_r1",
        "Test house",
        12,
    )
    assert "my_greenhouse_r1" in [
        each["id"] for each in _ask(simulator, "GET", "/api/scenarios")[1]
    ]
    status, scene = _ask(simulator, "GET", "/api/scenarios/my_greenhouse_r1/scene")
    assert status == HTTPStatus.OK
    assert scene["greenhouse_id"] == "my_greenhouse_r1"
    status, fields = _ask(simulator, "GET", "/api/scenarios/my_greenhouse_r1/fields")
    status, _ = _ask(
        simulator, "GET", f"/api/scenarios/my_greenhouse_r1/fields/{fields['configured']}"
    )
    assert status == HTTPStatus.OK
    status, crop = _ask(simulator, "GET", "/api/scenarios/my_greenhouse_r1/crop?t=86400")
    assert status == HTTPStatus.OK, crop
    # Asked again the same, it is the scenario already registered.
    assert _ask(simulator, "POST", f"/api/drafts/{DRAFT}/run", json.dumps(A_WEEK).encode()) == (
        HTTPStatus.OK,
        registered,
    )


def test_a_draft_runs_under_the_name_site_and_weather_it_is_given(simulator: Simulator) -> None:
    _save(simulator, _house())
    _save(simulator, _house(name="Later"), on=1)
    asked = A_WEEK | {
        "scenario_id": "spring_house",
        "name": "Spring house",
        "weather": "cold_spring_day",
        "site": {"latitude_deg": 45.0, "longitude_deg": 5.0, "time_zone": "Europe/Paris"},
    }

    status, registered = _ask(
        simulator, "POST", f"/api/drafts/{DRAFT}/run?revision=1", json.dumps(asked).encode()
    )

    assert (status, registered["id"], registered["name"]) == (
        HTTPStatus.OK,
        "spring_house",
        "Spring house",
    )
    status, manifest = _ask(simulator, "GET", "/api/scenarios/spring_house/manifest")
    assert (manifest["weather_kind"], manifest["duration_days"]) == ("synthetic", 7)
    status, weather = _ask(simulator, "GET", "/api/scenarios/spring_house/weather")
    assert weather["site"]["time_zone"] == "Europe/Paris"


def test_a_draft_that_cannot_run_or_a_run_that_is_not_one_is_refused(
    simulator: Simulator,
) -> None:
    _save(simulator, _house())
    mixed = assign_crop_to_rows(_house(), [2], crop_model=CropModel.SIMPLE, variety="beefsteak")
    _save(simulator, mixed, on=1)

    status, answer = _ask(
        simulator, "POST", f"/api/drafts/{DRAFT}/run", json.dumps(A_WEEK).encode()
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "at revision 2 cannot run: Rows grow different crops" in answer["error"]

    for asked, said in (
        ({"duration_days": 7}, "start_date: Field required"),
        (A_WEEK | {"duration_days": MOST_DAYS + 1}, "duration_days"),
        (A_WEEK | {"owner": "me"}, "owner"),
        (A_WEEK | {"scenario_id": "My House"}, "scenario_id"),
    ):
        status, answer = _ask(
            simulator, "POST", f"/api/drafts/{DRAFT}/run?revision=1", json.dumps(asked).encode()
        )
        assert (status, said in answer["error"]) == (HTTPStatus.BAD_REQUEST, True), answer
    status, answer = _ask(
        simulator,
        "POST",
        f"/api/drafts/{DRAFT}/run?revision=1",
        json.dumps(A_WEEK | {"weather": "monsoon"}).encode(),
    )
    assert (status, "no weather 'monsoon'" in answer["error"]) == (HTTPStatus.NOT_FOUND, True)


def test_a_draft_run_under_a_name_taken_is_a_conflict(simulator: Simulator) -> None:
    _save(simulator, _house())
    run = f"/api/drafts/{DRAFT}/run"

    packaged = A_WEEK | {"scenario_id": "climate_box"}
    status, answer = _ask(simulator, "POST", run, json.dumps(packaged).encode())
    assert (status, "is a packaged scenario" in answer["error"]) == (HTTPStatus.CONFLICT, True)
    assert _ask(simulator, "POST", run, json.dumps(A_WEEK).encode())[0] == HTTPStatus.OK
    longer = A_WEEK | {"duration_days": 14}
    status, answer = _ask(simulator, "POST", run, json.dumps(longer).encode())
    assert (status, "registered as another scenario" in answer["error"]) == (
        HTTPStatus.CONFLICT,
        True,
    )


def test_a_run_starts_on_a_day_the_simulator_works_out(simulator: Simulator) -> None:
    """A date far from now would be registered, and then fail every route
    that works out its sun or its weather."""
    _save(simulator, _house())
    for start in ("0001-01-01", "9999-12-31"):
        asked = A_WEEK | {"start_date": start}
        status, answer = _ask(
            simulator, "POST", f"/api/drafts/{DRAFT}/run", json.dumps(asked).encode()
        )
        assert (status, "start_date" in answer["error"]) == (HTTPStatus.BAD_REQUEST, True)


@pytest.mark.parametrize("revision", ["99999999999999999999", "9" * 5000, "-1", "1.0"])
def test_a_revision_too_large_to_keep_or_not_whole_is_refused(
    simulator: Simulator, revision: str
) -> None:
    _save(simulator, _house())

    for method, path in (
        ("GET", f"/api/drafts/{DRAFT}?revision={revision}"),
        ("POST", f"/api/drafts/{DRAFT}/revert?revision={revision}&on=1"),
        ("POST", f"/api/drafts/{DRAFT}/delete?on={revision}"),
    ):
        status, answer = _ask(simulator, method, path)
        assert (status, "is a revision, a whole number" in answer["error"]) == (
            HTTPStatus.BAD_REQUEST,
            True,
        )


def test_a_draft_named_as_no_scenario_is_runs_under_a_name_that_is(simulator: Simulator) -> None:
    house = _house().model_copy(update={"installation_id": "My-House.2"})
    _save(simulator, house)

    status, registered = _ask(
        simulator, "POST", "/api/drafts/My-House.2/run", json.dumps(A_WEEK).encode()
    )
    assert (status, registered["id"]) == (HTTPStatus.OK, "my_house_2_r1")


def test_a_run_the_scenario_refuses_says_why_in_words(simulator: Simulator) -> None:
    """A walkway across a row's first position leaves 11 for 2 rows of 6:
    the assessment has nothing against it, the scenario refuses it."""
    house = _house()
    walkway = {
        "primitive": "walkway",
        "fixture_id": "path",
        "start": {"x": 4.125, "y": 0.5},
        "end": {"x": 4.125, "y": 2.5},
        "width": 0.3,
    }
    layout = house.layout.model_validate(house.layout.model_dump() | {"placed": [walkway]})
    _save(simulator, house.model_copy(update={"layout": layout}))

    status, answer = _ask(
        simulator, "POST", f"/api/drafts/{DRAFT}/run", json.dumps(A_WEEK).encode()
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert "12 plants, but only 11 planting positions" in answer["error"]
    assert "pydantic" not in answer["error"] and "\n" not in answer["error"]


def test_a_revision_this_simulator_cannot_read_is_a_conflict(
    simulator: Simulator, tmp_path: Path
) -> None:
    """As one a later simulator saved, in a format this one does not read."""
    _save(simulator, _house())
    later = json.dumps(json.loads(export_installation(_house())) | {"schema_version": 99})
    with sqlite3.connect(tmp_path / "drafts.sqlite3") as connection:
        connection.execute("UPDATE revisions SET document = ?", (later,))

    for method, path in (
        ("GET", f"/api/drafts/{DRAFT}"),
        ("POST", f"/api/drafts/{DRAFT}/revert?revision=1&on=1"),
        ("POST", f"/api/drafts/{DRAFT}/run"),
    ):
        status, answer = _ask(simulator, method, path, json.dumps(A_WEEK).encode())
        assert (status, "cannot read" in answer["error"]) == (HTTPStatus.CONFLICT, True), answer


def test_a_file_the_store_could_not_read_back_is_refused(
    simulator: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sent compactly, a file may be read; kept as the store writes it, it
    may be too large to read back."""
    compact = json.dumps(json.loads(export_installation(_house())), separators=(",", ":"))
    monkeypatch.setattr(portable, "MAX_IMPORT_BYTES", len(compact) + 1)

    status, answer = _ask(simulator, "POST", f"/api/drafts/{DRAFT}/save", compact.encode())

    assert (status, "larger than" in answer["error"]) == (HTTPStatus.BAD_REQUEST, True)
    assert _ask(simulator, "GET", "/api/drafts") == (HTTPStatus.OK, [])


def test_the_api_keeps_drafts_where_it_is_told_or_starts_without_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = argparse.ArgumentParser()
    given = tmp_path / "given.sqlite3"
    assert server._drafts(given, parser) is not None
    assert given.exists()

    not_a_store = tmp_path / "notes.sqlite3"
    not_a_store.write_text("not a database\n" * 100)
    with pytest.raises(SystemExit):
        server._drafts(not_a_store, parser)

    # A home it may not write to: no drafts kept, and the API starts.
    home = tmp_path / "home"
    home.mkdir()
    home.chmod(0o555)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    try:
        assert server._drafts(None, parser) is None
    finally:
        home.chmod(0o755)
    assert "keeping no drafts" in capsys.readouterr().err
