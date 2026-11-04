"""A scenario file downloaded from one simulator and uploaded to another
(P17.11): validated, registered, kept beside the run store, and registered
again when a simulator is started on the store."""

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.builder.drafts import DraftStore
from greenhouse_sim.builder.portable import export_installation
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import scenario_installation
from greenhouse_sim.scenarios.scenario_files import RECORDED_WEATHER
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.run_store import FolderStore
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenario_files import KEPT_FOLDER
from greenhouse_sim.services.scenarios import weather_names
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.weather.recorded import RecordedWeather, checked_recording, recording_digest

MINE: Final = "my_box"
CSV: Final = (
    "timestamp,outside_air_temperature_c,outside_relative_humidity_pct\n"
    "2026-04-01T00:00Z,8,90\n2026-04-01T01:00Z,9,85\n"
)


def _mine(**changes: Any) -> ScenarioConfig:
    """A scenario of someone's own: a packaged one under another name."""
    return PACKAGED.configs["climate_box"].model_copy(
        update={"greenhouse_id": MINE, "name": "My box"} | changes
    )


def _recorded() -> RecordedWeather:
    return checked_recording("mine.csv", CSV.encode())


def _simulator(folder: Path) -> Simulator:
    return Simulator(runs=FolderStore(folder))


def _get(simulator: Simulator, path: str) -> tuple[HTTPStatus, Any]:
    answered = respond(simulator, "GET", path)
    return answered.status, answered.body


def _upload(simulator: Simulator, text: str) -> tuple[HTTPStatus, Any]:
    answered = respond(simulator, "POST", "/api/scenarios/upload", text.encode())
    return answered.status, answered.body


def _run_id(simulator: Simulator) -> str:
    return air_through_a_run(simulator, RunRequest(MINE))[1]


def _file(simulator: Simulator, query: str = "") -> str:
    status, body = _get(simulator, f"/api/scenarios/{MINE}/file{query}")
    assert status == HTTPStatus.OK
    return str(body["text"])


def _listed(simulator: Simulator) -> list[str]:
    _, body = _get(simulator, "/api/scenarios")
    return [each["id"] for each in body]


def test_a_downloaded_scenario_uploaded_to_a_clean_simulator_runs_as_the_original(
    tmp_path: Path,
) -> None:
    with _simulator(tmp_path / "a") as sender, _simulator(tmp_path / "b") as receiver:
        sender.catalogue.register(_mine())
        text = _file(sender)

        status, body = _upload(receiver, text)

        assert status == HTTPStatus.OK
        assert body["kind"] == "scenario"
        assert MINE in _listed(receiver)
        assert body["scenario"]["id"] == MINE and body["kept"]
        # It opens in the builder: the house, and the run's settings.
        assert body["installation"]["installation_id"] == MINE
        assert body["settings"]["scenario_id"] == MINE
        assert body["settings"]["duration_days"] == _mine().duration_days
        assert body["missing_weather"] is None
        assert _run_id(receiver) == _run_id(sender)


def test_a_recorded_weather_ticked_in_comes_with_the_file_and_gives_the_originals_run() -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine(weather=_recorded()))
        downloaded = _get(sender, f"/api/scenarios/{MINE}/file")[1]
        assert downloaded["has_recording"]
        assert json.loads(downloaded["text"])[RECORDED_WEATHER]["csv"] == CSV
        original = _run_id(sender)

        status, body = _upload(receiver, downloaded["text"])

        assert status == HTTPStatus.OK and body["scenario"] is not None
        assert _run_id(receiver) == original


def test_a_recorded_weather_ticked_out_leaves_the_scenario_unregistered_until_it_is_added(
    tmp_path: Path,
) -> None:
    with _simulator(tmp_path / "a") as sender, _simulator(tmp_path / "b") as receiver:
        sender.catalogue.register(_mine(weather=_recorded()))
        bare = _get(sender, f"/api/scenarios/{MINE}/file?recording=0")[1]
        full = _file(sender)
        assert not bare["has_recording"] and "csv" not in json.loads(bare["text"])[RECORDED_WEATHER]

        status, body = _upload(receiver, bare["text"])

        # Read, and offered to the builder, but not a scenario that can run.
        assert status == HTTPStatus.OK
        assert body["scenario"] is None and not body["kept"]
        assert body["installation"]["installation_id"] == MINE
        assert body["missing_weather"] == {
            "file": "mine.csv",
            "digest": recording_digest(CSV.encode()),
        }
        assert MINE not in _listed(receiver)
        assert FolderStore(tmp_path / "b").names(KEPT_FOLDER) == []
        assert _upload(receiver, full)[1]["scenario"]["id"] == MINE


def test_the_same_file_again_is_the_scenario_already_registered(tmp_path: Path) -> None:
    with _simulator(tmp_path / "a") as sender, _simulator(tmp_path / "b") as receiver:
        sender.catalogue.register(_mine())
        text = _file(sender)

        first, second = _upload(receiver, text)[1], _upload(receiver, text)[1]

        assert first["file_digest"] == second["file_digest"]
        assert _listed(receiver).count(MINE) == 1
        assert len(FolderStore(tmp_path / "b").names(KEPT_FOLDER)) == 1


def test_a_scenario_named_as_a_packaged_one_or_another_registered_is_refused() -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine())
        text = _file(sender)
        packaged = text.replace(f'"greenhouse_id": "{MINE}"', '"greenhouse_id": "climate_box"')
        assert _upload(receiver, text)[0] == HTTPStatus.OK
        other = json.dumps(json.loads(text) | {"duration_days": 3})

        status, body = _upload(receiver, packaged)
        assert status == HTTPStatus.CONFLICT and "packaged scenario" in body["error"]
        status, body = _upload(receiver, other)
        assert status == HTTPStatus.CONFLICT and "registered as another scenario" in body["error"]


def test_a_scenario_uploaded_is_registered_again_when_a_simulator_starts_on_the_store(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    with Simulator() as sender:
        sender.catalogue.register(_mine(weather=_recorded()))
        text = _file(sender)
        original = _run_id(sender)
    with _simulator(store) as first:
        assert _upload(first, text)[0] == HTTPStatus.OK

    with _simulator(store) as second:
        assert MINE in _listed(second)
        assert _run_id(second) == original


def test_a_kept_file_that_cannot_be_read_does_not_stop_the_others(tmp_path: Path) -> None:
    store = FolderStore(tmp_path / "store")
    with Simulator() as sender:
        sender.catalogue.register(_mine())
        text = _file(sender)
    with Simulator(runs=store) as first:
        assert _upload(first, text)[0] == HTTPStatus.OK
    store.put(f"{KEPT_FOLDER}broken.json", b'{"schema_version": 99}')
    store.put(f"{KEPT_FOLDER}binary.json", b"\xff\xfe")

    with Simulator(runs=store) as second:
        assert MINE in _listed(second)


def test_a_recording_under_a_packaged_ones_name_with_other_content_is_kept_under_a_digest_name(
    tmp_path: Path,
) -> None:
    other = CSV.encode()
    with Simulator() as sender, _simulator(tmp_path) as receiver:
        sender.catalogue.register(_mine(weather=RecordedWeather(file="example_day.csv")))
        document = json.loads(_file(sender))
        document[RECORDED_WEATHER] |= {"csv": CSV, "digest": recording_digest(other)}

        status, _ = _upload(receiver, json.dumps(document))

        assert status == HTTPStatus.OK
        scenario = receiver.catalogue.entry(MINE)
        assert scenario is not None
        weather = scenario.config.weather
        assert isinstance(weather, RecordedWeather)
        assert weather.file == f"example_day-{recording_digest(other)[:12]}.csv"
        assert weather.identity() == recording_digest(other)
        assert RecordedWeather(file="example_day.csv").identity() != recording_digest(other)


@pytest.mark.parametrize(
    ("change", "field"),
    [
        (lambda d: d.update(schema_version=99), "schema_version"),
        (lambda d: d.update(extra=1), ""),
        (lambda d: d.update(duration_days=-1), "duration_days"),
    ],
    ids=["version", "unknown field", "value"],
)
def test_a_file_that_is_not_a_scenario_is_refused_naming_the_field(change: Any, field: str) -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine())
        document = json.loads(_file(sender))
        change(document)

        status, body = _upload(receiver, json.dumps(document))

        assert status == HTTPStatus.BAD_REQUEST
        assert body["error"].startswith("not a scenario file")
        assert [problem["field"] for problem in body["problems"]] == [field]
        assert MINE not in _listed(receiver)


def _house_file() -> str:
    """An installation's file, as the builder's export writes one."""
    return export_installation(scenario_installation(_mine()))


def test_an_installation_file_uploaded_answers_its_house_and_registers_nothing(
    tmp_path: Path,
) -> None:
    store = FolderStore(tmp_path / "runs")
    drafts = DraftStore(tmp_path / "drafts.sqlite3")
    with Simulator(runs=store, drafts=drafts) as receiver:
        status, body = _upload(receiver, _house_file())

        assert status == HTTPStatus.OK
        assert body["kind"] == "installation"
        assert body["assessed"]["installation"]["installation_id"] == MINE
        assert isinstance(body["assessed"]["findings"], list)
        # It has no run settings to be a scenario by: it waits for the builder's.
        assert MINE not in _listed(receiver)
        assert store.names(KEPT_FOLDER) == []
        assert drafts.drafts() == []


def test_an_installation_file_uploaded_leaves_a_draft_of_its_identifier_as_it_is(
    tmp_path: Path,
) -> None:
    with Simulator(drafts=DraftStore(tmp_path / "drafts.sqlite3")) as receiver:
        text = _house_file()
        saved = respond(receiver, "POST", f"/api/drafts/{MINE}/save", text.encode())
        assert saved.status == HTTPStatus.OK
        changed = json.loads(text) | {"name": "Another house"}

        status, _ = _upload(receiver, json.dumps(changed))
        _, kept = _get(receiver, f"/api/drafts/{MINE}")
        # A save as a new draft, as the builder's of a file opened, is refused.
        again = respond(receiver, "POST", f"/api/drafts/{MINE}/save", json.dumps(changed).encode())

        assert status == HTTPStatus.OK
        assert (kept["draft"]["revision"], kept["installation"]["name"]) == (
            1,
            json.loads(text)["name"],
        )
        assert again.status == HTTPStatus.CONFLICT


def test_a_malformed_installation_file_gets_the_builders_refusal_naming_the_field() -> None:
    document = json.loads(_house_file())
    del document["envelope"]
    with Simulator() as receiver:
        status, body = _upload(receiver, json.dumps(document))

    assert status == HTTPStatus.BAD_REQUEST
    assert body["error"].startswith("not a house file: envelope:")
    assert [problem["field"] for problem in body["problems"]] == ["envelope"]


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ('{"schema_version": 7, "name": "A note"}', "this file has neither"),
        ('{"greenhouse_id": null, "installation_id": null}', "this file has neither"),
        ("[]", "not a JSON object"),
        ("my house", "not JSON"),
    ],
    ids=["neither", "both empty", "a list", "not json"],
)
def test_a_file_of_neither_kind_is_told_what_it_needs_to_be(text: str, said: str) -> None:
    with Simulator() as receiver:
        status, body = _upload(receiver, text)

    assert status == HTTPStatus.BAD_REQUEST
    assert body["error"].startswith("not a scenario file or a house file: ")
    assert said in body["error"]
    assert "None" not in body["error"]


def test_a_file_naming_both_is_read_as_a_scenario_and_refused_for_the_other_name() -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine())
        document = json.loads(_file(sender)) | {"installation_id": MINE}

        status, body = _upload(receiver, json.dumps(document))

        assert status == HTTPStatus.BAD_REQUEST
        assert body["error"].startswith("not a scenario file: ")
        assert MINE not in _listed(receiver)


def test_a_file_over_the_limit_or_not_text_is_refused() -> None:
    with Simulator() as receiver:
        big = respond(receiver, "POST", "/api/scenarios/upload", b" " * 8_000_001)
        binary = respond(receiver, "POST", "/api/scenarios/upload", b"\xff\xfe")

        assert big.status == HTTPStatus.BAD_REQUEST and "larger than" in str(big.body)
        assert binary.status == HTTPStatus.BAD_REQUEST and "UTF-8" in str(binary.body)


def test_an_unknown_scenario_has_no_file_and_one_that_cannot_be_written_is_refused() -> None:
    reference = PACKAGED.configs["reference_greenhouse"]
    with Simulator() as simulator:
        simulator.catalogue.register(
            reference.model_copy(update={"greenhouse_id": MINE, "rows": reference.rows - 1})
        )

        assert _get(simulator, "/api/scenarios/nothing/file")[0] == HTTPStatus.NOT_FOUND
        status, body = _get(simulator, f"/api/scenarios/{MINE}/file")
        assert status == HTTPStatus.BAD_REQUEST
        assert "cannot be written as a file" in str(body)


def test_a_recording_belongs_to_the_simulator_that_registered_it() -> None:
    names = weather_names()
    with Simulator() as sender, Simulator() as first, Simulator() as second:
        sender.catalogue.register(_mine(weather=_recorded()))
        full = _file(sender)
        bare = _get(sender, f"/api/scenarios/{MINE}/file?recording=0")[1]["text"]
        packaged = full.replace(f'"greenhouse_id": "{MINE}"', '"greenhouse_id": "climate_box"')

        # A refused upload leaves its recording nowhere.
        assert _upload(first, packaged)[0] == HTTPStatus.CONFLICT
        assert _upload(first, bare)[1]["missing_weather"] is not None
        # An accepted one gives it to this simulator alone.
        assert _upload(first, full)[0] == HTTPStatus.OK
        assert _upload(second, bare)[1]["missing_weather"] is not None
        assert weather_names() == names


def test_a_file_without_its_recording_takes_it_from_a_scenario_that_carries_it() -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine(weather=_recorded()))
        full = _file(sender)
        bare = _get(sender, f"/api/scenarios/{MINE}/file?recording=0")[1]["text"]
        another = bare.replace(f'"greenhouse_id": "{MINE}"', '"greenhouse_id": "another_box"')

        assert _upload(receiver, full)[0] == HTTPStatus.OK
        status, body = _upload(receiver, another)

        assert status == HTTPStatus.OK and body["missing_weather"] is None
        entry = receiver.catalogue.entry("another_box")
        assert entry is not None and isinstance(entry.config.weather, RecordedWeather)
        assert entry.config.weather.identity() == recording_digest(CSV.encode())


def test_a_kept_file_waits_for_the_recording_another_carries(tmp_path: Path) -> None:
    store = FolderStore(tmp_path / "store")
    with Simulator() as sender:
        sender.catalogue.register(_mine(weather=_recorded()))
        full = _file(sender)
        bare = _get(sender, f"/api/scenarios/{MINE}/file?recording=0")[1]["text"]
    another = bare.replace(f'"greenhouse_id": "{MINE}"', '"greenhouse_id": "another_box"')
    # The store lists the file that needs the recording before the one that has it.
    store.put(f"{KEPT_FOLDER}0-needs.json", another.encode())
    store.put(f"{KEPT_FOLDER}1-carries.json", full.encode())

    with Simulator(runs=store) as simulator:
        assert {MINE, "another_box"} <= set(_listed(simulator))


def test_a_run_settings_range_is_the_scenarios_own() -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine())
        long = json.dumps(json.loads(_file(sender)) | {"duration_days": 367})

        status, body = _upload(receiver, long)

        # A draft's run is limited to 366 days; a scenario's is not.
        assert status == HTTPStatus.OK
        assert body["settings"]["duration_days"] == 367


def test_a_name_an_installation_cannot_have_is_refused_not_failed() -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine())
        unnamed = json.dumps(json.loads(_file(sender)) | {"name": ""})

        status, body = _upload(receiver, unnamed)

        assert status == HTTPStatus.BAD_REQUEST and "not a scenario file" in body["error"]


def test_a_recording_of_other_content_is_not_taken_for_the_one_a_file_names() -> None:
    with Simulator() as sender, Simulator() as receiver:
        sender.catalogue.register(_mine(weather=_recorded()))
        full = _file(sender)
        bare = json.loads(_get(sender, f"/api/scenarios/{MINE}/file?recording=0")[1]["text"])
        bare["greenhouse_id"] = "another_box"
        bare[RECORDED_WEATHER]["digest"] = recording_digest(b"other")

        assert _upload(receiver, full)[0] == HTTPStatus.OK
        body = _upload(receiver, json.dumps(bare))[1]

        assert body["scenario"] is None and body["missing_weather"]["file"] == "mine.csv"
