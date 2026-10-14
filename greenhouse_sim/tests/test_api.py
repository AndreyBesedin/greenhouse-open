"""The local API the viewer talks to: what it answers, over real HTTP, and
that the simulator never depends on it.

The simulator's own tests do not import the API; this module is the only
one that does, apart from the boundary check below.
"""

import ast
import http.client
import json
import pathlib
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from greenhouse_sim.api import server as server_module
from greenhouse_sim.api.routes import Response, respond
from greenhouse_sim.api.server import UNEXPECTED_FAILURE, create_server
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.manifest_files import manifest_digest, opening_day
from greenhouse_sim.scene.snapshot import SCHEMA_VERSION, SceneEntityKind, SceneSnapshot
from greenhouse_sim.services import system

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "greenhouse_sim"
# Long enough for any answer of the local server's.
WAIT_S = 10.0


def test_the_health_check_answers() -> None:
    response = respond("GET", "/api/health")

    assert (response.status, response.body) == (HTTPStatus.OK, {"status": "ok"})


def test_the_version_names_the_simulator_its_commit_and_the_scene_schema() -> None:
    body = respond("GET", "/api/version").body

    assert isinstance(body, dict)
    assert body["simulator"] == "greenhouse-sim"
    assert body["scene_schema_version"] == SCHEMA_VERSION
    assert isinstance(body["version"], str) and body["version"]
    # Run from a git checkout, the commit is git's abbreviation of its HEAD;
    # installed as a package, as CI installs it, it is unknown.
    assert body["commit"] == system.source_commit()
    assert re.fullmatch(r"[0-9a-f]{7,}|unknown", str(body["commit"]))


def test_the_commit_is_gits_abbreviation_of_the_checkouts_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[object] = []

    def git(arguments: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        asked.append((arguments, options["cwd"]))
        return subprocess.CompletedProcess(arguments, 0, stdout="c1964e9\n")

    monkeypatch.setattr(subprocess, "run", git)

    assert system.source_commit.__wrapped__() == "c1964e9"
    # Asked where the simulator's source lies, not where it was started.
    assert asked == [
        (["git", "rev-parse", "--short", "HEAD"], pathlib.Path(system.__file__).parent)
    ]


@pytest.mark.parametrize(
    "failure",
    [FileNotFoundError("git"), subprocess.CalledProcessError(128, "git"), OSError("denied")],
)
def test_outside_a_git_checkout_the_commit_is_unknown(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(subprocess, "run", fail)

    assert system.source_commit.__wrapped__() == system.UNKNOWN_COMMIT


def test_a_runs_manifest_is_served_and_refused_as_its_run_is() -> None:
    body = respond("GET", "/api/scenarios/reference_greenhouse/manifest?weather=default~90").body

    assert isinstance(body, dict)
    assert body["version"] == manifest_digest("reference_greenhouse")
    assert (body["random_seed"], body["start_date"], body["opening_day"]) == (42, "2026-03-01", 80)
    assert (body["weather"], body["wind_from_deg"]) == ("default", 90.0)
    assert respond("GET", "/api/scenarios/nowhere/manifest").status == HTTPStatus.NOT_FOUND
    refused = respond("GET", "/api/scenarios/climate_box/manifest?weather=default~400")
    assert refused.status == HTTPStatus.BAD_REQUEST


# The scenarios with more than their default layout, and their others.
OTHER_LAYOUTS = {
    "airflow_box": ["open"],
    "tomato_compartment": ["propagation"],
    "sensor_lab": ["blocked"],
}


def test_the_scenario_list_is_the_registry() -> None:
    body = respond("GET", "/api/scenarios").body

    assert isinstance(body, list)
    summaries = {item["id"]: item for item in body if isinstance(item, dict)}
    assert set(summaries) == set(SCENARIO_REGISTRY)
    for scenario_id, config in SCENARIO_REGISTRY.items():
        assert summaries[scenario_id] == {
            "id": scenario_id,
            "name": config.name,
            "description": config.description,
            "plants": config.rows * config.columns,
            "duration_days": config.duration_days,
            "crop_model": config.crop_model.value,
            "daily": [command.model_dump(mode="json") for command in config.daily],
            "openings": [opening.opening_id for opening in config.envelope.openings],
            "opening_day": opening_day(scenario_id),
            "layouts": ["default", *OTHER_LAYOUTS.get(scenario_id, [])],
            "weathers": [
                "default",
                "cold_spring_day",
                "hot_dry_summer_day",
                "windy_autumn_day",
                "example_day",
            ],
        }


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_REGISTRY))
def test_a_scenario_has_a_scene_before_its_first_day(scenario_id: str) -> None:
    response = respond("GET", f"/api/scenarios/{scenario_id}/scene")
    config = SCENARIO_REGISTRY[scenario_id]

    assert response.status == HTTPStatus.OK
    snapshot = SceneSnapshot.model_validate(response.body)
    # Its whole crop: each plant a stem, or organ by organ.
    plants = {e.entity_id for e in snapshot.entities if e.kind == SceneEntityKind.PLANT} | {
        e.properties["plant_id"] for e in snapshot.entities if "organ_id" in e.properties
    }
    assert (snapshot.greenhouse_id, snapshot.simulated_day) == (scenario_id, 0)
    assert len(plants) == config.rows * config.columns


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/api/scenarios/no_such_scenario/scene", HTTPStatus.NOT_FOUND),
        ("GET", "/api/nothing_here", HTTPStatus.NOT_FOUND),
        ("GET", "/", HTTPStatus.NOT_FOUND),
        ("POST", "/api/health", HTTPStatus.METHOD_NOT_ALLOWED),
    ],
)
def test_anything_else_is_refused_with_a_reason(method: str, path: str, status: HTTPStatus) -> None:
    response = respond(method, path)

    assert response.status == status
    assert isinstance(response.body, dict) and response.body["error"]


@pytest.fixture
def server() -> Iterator[ThreadingHTTPServer]:
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def test_the_server_answers_over_http_on_the_loopback_interface(
    server: ThreadingHTTPServer,
) -> None:
    host, port = server.server_address[:2]
    assert host == "127.0.0.1"

    with urllib.request.urlopen(f"http://{host!s}:{port}/api/scenarios") as reply:
        assert reply.headers["Content-Type"] == "application/json"
        assert {item["id"] for item in json.load(reply)} == set(SCENARIO_REGISTRY)

    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(f"http://{host!s}:{port}/api/nothing_here")
    assert refused.value.code == HTTPStatus.NOT_FOUND
    assert json.load(refused.value)["error"]


def test_every_answer_says_how_long_the_simulator_took(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    host, port = server.server_address[:2]
    took = re.compile(r"sim;dur=(\d+\.\d)")

    with urllib.request.urlopen(f"http://{host!s}:{port}/api/health") as reply:
        assert took.fullmatch(reply.headers["Server-Timing"])
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(f"http://{host!s}:{port}/api/nothing_here")
    assert took.fullmatch(refused.value.headers["Server-Timing"])

    # The time is the simulator's, from the request read to its answer
    # written as JSON.
    def slow(method: str, path: str) -> Response:
        time.sleep(0.05)
        return Response(HTTPStatus.OK, {"status": "ok"})

    monkeypatch.setattr(server_module, "respond", slow)
    with urllib.request.urlopen(f"http://{host!s}:{port}/api/health") as reply:
        found = took.fullmatch(reply.headers["Server-Timing"])
    assert found is not None and float(found.group(1)) >= 50


def test_a_body_with_a_number_json_does_not_have_is_refused() -> None:
    for constant in ("NaN", "Infinity", "-Infinity"):
        response = respond("POST", "/api/checkpoints", f'{{"day": {constant}}}'.encode())

        assert response.status == HTTPStatus.BAD_REQUEST
        assert isinstance(response.body, dict)
        assert constant in str(response.body["error"])


def _posted(server: ThreadingHTTPServer, length: str, body: bytes = b"") -> tuple[int, Any]:
    """POSTs `body` to the checkpoints, its `Content-Length` said to be
    `length`; the answer's status and body."""
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(str(host), port, timeout=WAIT_S)
    connection.putrequest("POST", "/api/checkpoints")
    connection.putheader("Content-Length", length)
    connection.endheaders(body)
    reply = connection.getresponse()
    answer = reply.status, json.load(reply)
    connection.close()
    return answer


@pytest.mark.parametrize("length", ["abc", "-5", "1.5"])
def test_a_body_whose_length_is_not_one_is_refused(
    server: ThreadingHTTPServer, length: str
) -> None:
    status, body = _posted(server, length)

    assert status == HTTPStatus.BAD_REQUEST
    assert "not a length" in body["error"]


def test_a_body_larger_than_the_api_reads_is_refused_unread(server: ThreadingHTTPServer) -> None:
    status, body = _posted(server, str(server_module.MAX_BODY_BYTES + 1))

    assert status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert "at most" in body["error"]


def test_a_body_shorter_than_announced_is_answered_once_the_client_stops(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server_module._Handler, "timeout", 0.2)
    host, port = server.server_address[:2]

    with socket.create_connection((str(host), port), timeout=WAIT_S) as client:
        client.sendall(b"POST /api/checkpoints HTTP/1.1\r\nContent-Length: 100\r\n\r\n{}")
        reply = client.makefile("rb").read()

    assert reply.startswith(b"HTTP/1.0 408")
    assert b"stopped short of the 100 bytes announced" in reply


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_another_method_is_refused_as_json_with_its_timing(
    server: ThreadingHTTPServer, method: str
) -> None:
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(str(host), port, timeout=WAIT_S)
    connection.request(method, "/api/checkpoints")
    reply = connection.getresponse()

    assert reply.status == HTTPStatus.METHOD_NOT_ALLOWED
    assert reply.headers["Server-Timing"].startswith("sim;dur=")
    assert method in json.load(reply)["error"]
    connection.close()


def test_a_request_the_simulator_fails_on_is_answered_500_and_logged(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing(method: str, path: str) -> Response:
        raise RuntimeError("a failure nobody planned for")

    monkeypatch.setattr(server_module, "respond", failing)
    host, port = server.server_address[:2]

    with pytest.raises(urllib.error.HTTPError) as failed:
        urllib.request.urlopen(f"http://{host!s}:{port}/api/health")

    assert failed.value.code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert json.load(failed.value) == {"error": UNEXPECTED_FAILURE}
    assert "a failure nobody planned for" in capsys.readouterr().err


def test_nothing_in_the_simulator_imports_its_api() -> None:
    """The API is an adapter around the simulator, never a dependency of it."""
    importers = sorted(
        f"{path.relative_to(PACKAGE).as_posix()}:{node.lineno}"
        for path in PACKAGE.rglob("*.py")
        if not path.relative_to(PACKAGE).as_posix().startswith("api/")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("greenhouse_sim.api")
        or isinstance(node, ast.Import)
        and any(alias.name.startswith("greenhouse_sim.api") for alias in node.names)
    )
    assert not importers, importers
