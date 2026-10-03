"""What the local API answers, independent of HTTP.

`respond` maps a method and a path to a status and a JSON-ready body, so the
API can be tested without a socket and the server stays a thin shell.

    GET /api/health                       the API is up
    GET /api/version                      simulator and scene schema versions
    GET /api/scenarios                    the registered scenarios
    GET /api/scenarios/{id}/scene         a scenario's scene before its first day
    GET /api/scenarios/{id}/live          the scenario played live, as Server-Sent
                                          Events (served by `server`, found by
                                          `live_scenario`)
"""

from dataclasses import dataclass
from http import HTTPStatus
from importlib.metadata import version

from pydantic import BaseModel

from greenhouse_sim.core.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scene.snapshot import SCHEMA_VERSION, scene_snapshot

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None


@dataclass(frozen=True)
class Response:
    status: HTTPStatus
    body: JsonValue


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str
    plants: int
    duration_days: int


def respond(method: str, path: str) -> Response:
    if method != "GET":
        return _error(HTTPStatus.METHOD_NOT_ALLOWED, "only GET is supported")

    segments = [segment for segment in path.split("?", 1)[0].split("/") if segment]
    match segments:
        case ["api", "health"]:
            return Response(HTTPStatus.OK, {"status": "ok"})
        case ["api", "version"]:
            return Response(HTTPStatus.OK, _version())
        case ["api", "scenarios"]:
            summaries = [_summary(config) for config in SCENARIO_REGISTRY.values()]
            return Response(HTTPStatus.OK, [summary.model_dump() for summary in summaries])
        case ["api", "scenarios", scenario_id, "scene"]:
            config = SCENARIO_REGISTRY.get(scenario_id)
            if config is None:
                return _error(HTTPStatus.NOT_FOUND, f"no scenario {scenario_id!r}")
            return Response(HTTPStatus.OK, _initial_scene(config))
        case _:
            return _error(HTTPStatus.NOT_FOUND, f"nothing at {path!r}")


def _version() -> JsonValue:
    return {
        "simulator": "greenhouse-sim",
        "version": version("greenhouse-sim"),
        "scene_schema_version": SCHEMA_VERSION,
    }


def _summary(config: ScenarioConfig) -> ScenarioSummary:
    return ScenarioSummary(
        id=config.greenhouse_id,
        name=config.name,
        description=config.description,
        plants=config.rows * config.columns,
        duration_days=config.duration_days,
    )


def _initial_scene(config: ScenarioConfig) -> JsonValue:
    """The scenario's full crop before its first day, as the viewer draws it."""
    plant_count = config.rows * config.columns
    plant_ids = [f"{config.greenhouse_id}_plant_{i:03d}" for i in range(1, plant_count + 1)]
    world = SimulationEngine(config).initialize(plant_ids, greenhouse_id=config.greenhouse_id)
    snapshot: JsonValue = scene_snapshot(world, config).model_dump(mode="json")
    return snapshot


def _error(status: HTTPStatus, message: str) -> Response:
    return Response(status, {"error": message})


def live_scenario(path: str) -> ScenarioConfig | None:
    """The scenario a request for its live stream names, if it names one."""
    segments = [segment for segment in path.split("?", 1)[0].split("/") if segment]
    match segments:
        case ["api", "scenarios", scenario_id, "live"]:
            return SCENARIO_REGISTRY.get(scenario_id)
        case _:
            return None
