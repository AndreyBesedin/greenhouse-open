"""The local API the viewer talks to: what it answers, over real HTTP, and
that the simulator never depends on it.

The simulator's own tests do not import the API; this module is the only
one that does, apart from the boundary check below.
"""

import ast
import json
import pathlib
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http import HTTPStatus
from http.server import ThreadingHTTPServer

import pytest

from greenhouse_sim.api import server as server_module
from greenhouse_sim.api.routes import Response, respond
from greenhouse_sim.api.server import UNEXPECTED_FAILURE, create_server
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SCHEMA_VERSION, SceneEntityKind, SceneSnapshot

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "greenhouse_sim"


def test_the_health_check_answers() -> None:
    response = respond("GET", "/api/health")

    assert (response.status, response.body) == (HTTPStatus.OK, {"status": "ok"})


def test_the_version_names_the_simulator_and_the_scene_schema() -> None:
    body = respond("GET", "/api/version").body

    assert isinstance(body, dict)
    assert body["simulator"] == "greenhouse-sim"
    assert body["scene_schema_version"] == SCHEMA_VERSION
    assert isinstance(body["version"], str) and body["version"]


# The scenarios with more than their default layout, and their others.
OTHER_LAYOUTS = {"gh_001": ["benches"], "airflow_box": ["open"]}


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
            "layouts": ["default", *OTHER_LAYOUTS.get(scenario_id, [])],
        }


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_REGISTRY))
def test_a_scenario_has_a_scene_before_its_first_day(scenario_id: str) -> None:
    response = respond("GET", f"/api/scenarios/{scenario_id}/scene")
    config = SCENARIO_REGISTRY[scenario_id]

    assert response.status == HTTPStatus.OK
    snapshot = SceneSnapshot.model_validate(response.body)
    plants = [e for e in snapshot.entities if e.kind == SceneEntityKind.PLANT]
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
