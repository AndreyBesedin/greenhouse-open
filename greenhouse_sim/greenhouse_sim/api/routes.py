"""What the local API answers, independent of HTTP.

`respond` maps a method and a path to a status and a JSON-ready body, so the
API can be tested without a socket and the server stays a thin shell.

    GET /api/health                       the API is up
    GET /api/version                      simulator and scene schema versions
    GET /api/scenarios                    the registered scenarios, with the
                                          names of their layouts
    GET /api/scenarios/{id}/scene         a scenario's scene before its first day;
                                          ?layout=benches shows another of its
                                          layouts, ?envelope=length:12,spans:3
                                          changes its greenhouse's dimensions,
                                          and ?open=roof_vent_1:0.5,door_1:1 how
                                          far its doors and vents stand open
    GET /api/scenarios/{id}/layout        a scenario's layout, as its file holds
                                          it; ?layout=benches another of them
    GET /api/scenarios/{id}/live          the scenario played live, as Server-Sent
                                          Events (served by `server`, found by
                                          `live_scenario`)
    POST /api/scenarios/{id}/live/...     commands for that live run (`control`)
"""

from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from importlib.metadata import version
from typing import Final
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ValidationError

from greenhouse_sim.api.live import SPEEDS, LiveFrame, LiveRun, LiveRuns
from greenhouse_sim.core.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import (
    DEFAULT_LAYOUT,
    layout_document,
    layout_names,
    load_layout,
)
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
    # Its layouts' names, its default first.
    layouts: list[str]


def respond(method: str, path: str) -> Response:
    if method != "GET":
        return _error(HTTPStatus.METHOD_NOT_ALLOWED, f"{path!r} only answers GET")

    match _segments(path):
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
            query = parse_qs(urlsplit(path).query)
            laid_out = _with_layout(config, query.get("layout", [DEFAULT_LAYOUT])[-1])
            if isinstance(laid_out, Response):
                return laid_out
            changed = _with_envelope(laid_out, query.get("envelope", []), query.get("open", []))
            if isinstance(changed, str):
                return _error(HTTPStatus.BAD_REQUEST, changed)
            return Response(HTTPStatus.OK, _initial_scene(changed))
        case ["api", "scenarios", scenario_id, "layout"]:
            config = SCENARIO_REGISTRY.get(scenario_id)
            if config is None:
                return _error(HTTPStatus.NOT_FOUND, f"no scenario {scenario_id!r}")
            query = parse_qs(urlsplit(path).query)
            laid_out = _with_layout(config, query.get("layout", [DEFAULT_LAYOUT])[-1])
            if isinstance(laid_out, Response):
                return laid_out
            return Response(HTTPStatus.OK, layout_document(laid_out.layout))
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
        layouts=layout_names(config.greenhouse_id),
    )


def _with_layout(config: ScenarioConfig, name: str) -> ScenarioConfig | Response:
    """The scenario with another of its layouts, read from its file, or why it
    cannot have it: a layout it does not have, or one that does not fit its
    greenhouse or crop."""
    if name == DEFAULT_LAYOUT:
        return config
    try:
        layout = load_layout(config.greenhouse_id, name)
    except KeyError:
        return _error(HTTPStatus.NOT_FOUND, f"{config.greenhouse_id} has no layout {name!r}")
    except ValidationError as error:
        return _error(HTTPStatus.BAD_REQUEST, f"no such layout: {error.errors()[0]['msg']}")
    try:
        return ScenarioConfig.model_validate(config.model_dump() | {"layout": layout})
    except ValidationError as error:
        return _error(HTTPStatus.BAD_REQUEST, f"no such layout: {error.errors()[0]['msg']}")


# The envelope's dimensions a scene request may change.
_DIMENSIONS: Final = ("length", "width", "spans", "bays", "eave_height", "ridge_height")


def _pairs(requests: list[str], name: str) -> dict[str, float] | str:
    """`name=key:number,key:number` as numbers by key, or why it cannot be read."""
    pairs: dict[str, float] = {}
    for request in ",".join(requests).split(","):
        if not request:
            continue
        key, _, number = request.partition(":")
        try:
            pairs[key] = float(number)
        except ValueError:
            return f"{name} wants key:number pairs, not {request!r}"
    return pairs


def _with_envelope(
    config: ScenarioConfig, dimensions: list[str], openings: list[str]
) -> ScenarioConfig | str:
    """The scenario with its greenhouse's dimensions changed as
    `envelope=length:12,spans:3,...` asks, and its doors and vents opened as
    `open=id:fraction,...` asks, or why it cannot be. The envelope is checked
    afresh, as any description of a greenhouse is: an opening that no longer
    fits, or a ridge below the eaves, is refused, as is a greenhouse the
    scenario's layout no longer fits in."""
    sizes = _pairs(dimensions, "envelope")
    if isinstance(sizes, str):
        return sizes
    unknown_sizes = sorted(set(sizes) - set(_DIMENSIONS))
    if unknown_sizes:
        named = ", ".join(map(repr, unknown_sizes))
        return f"the envelope has no {named}; it has {', '.join(_DIMENSIONS)}"
    fractions = _pairs(openings, "open")
    if isinstance(fractions, str):
        return fractions
    envelope = config.envelope
    known = {opening.opening_id for opening in envelope.openings}
    unknown = sorted(set(fractions) - known)
    if unknown:
        return f"{config.greenhouse_id} has no opening {', '.join(map(repr, unknown))}"
    opened = [
        opening.model_dump() | {"opening": fractions.get(opening.opening_id, opening.opening)}
        for opening in envelope.openings
    ]
    try:
        changed = type(envelope).model_validate(
            envelope.model_dump() | sizes | {"openings": opened}
        )
        return ScenarioConfig.model_validate(config.model_dump() | {"envelope": changed})
    except ValidationError as error:
        return f"no such greenhouse: {error.errors()[0]['msg']}"


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
    match _segments(path):
        case ["api", "scenarios", scenario_id, "live"]:
            return SCENARIO_REGISTRY.get(scenario_id)
        case _:
            return None


_COMMANDS: Final[dict[str, Callable[[LiveRun], LiveFrame]]] = {
    "play": LiveRun.play,
    "pause": LiveRun.pause,
    "step": LiveRun.advance,
    "reset": LiveRun.reset,
}


def control(path: str, runs: LiveRuns) -> Response | None:
    """Applies a command to a scenario's live run, if `path` names one.

        POST /api/scenarios/{id}/live/play                 play on from the current day
        POST /api/scenarios/{id}/live/pause                hold the current day
        POST /api/scenarios/{id}/live/step                 one simulated day on
        POST /api/scenarios/{id}/live/reset                back to before day one
        POST /api/scenarios/{id}/live/speed?multiplier=2   play faster or slower

    The answer is the run's new state without its scene, which reaches every
    viewer on the stream.
    """
    url = urlsplit(path)
    match _segments(url.path):
        case ["api", "scenarios", scenario_id, "live", command]:
            pass
        case _:
            return None
    config = SCENARIO_REGISTRY.get(scenario_id)
    if config is None:
        return _error(HTTPStatus.NOT_FOUND, f"no scenario {scenario_id!r}")
    if command == "speed":
        speed = _speed(parse_qs(url.query).get("multiplier", []))
        if speed is None:
            allowed = ", ".join(f"{speed:g}" for speed in SPEEDS)
            return _error(HTTPStatus.BAD_REQUEST, f"multiplier must be one of {allowed}")
        return _state(runs.run_for(config).set_speed(speed))
    act = _COMMANDS.get(command)
    if act is None:
        return _error(HTTPStatus.NOT_FOUND, f"no live command {command!r}")
    return _state(act(runs.run_for(config)))


def _speed(values: list[str]) -> float | None:
    """The one speed a query asks for, if it is one the runs accept."""
    if len(values) != 1:
        return None
    try:
        speed = float(values[0])
    except ValueError:
        return None
    return speed if speed in SPEEDS else None


def _state(frame: LiveFrame) -> Response:
    state: JsonValue = frame.model_dump(mode="json", exclude={"snapshot"})
    return Response(HTTPStatus.OK, state)


def _segments(path: str) -> list[str]:
    return [segment for segment in urlsplit(path).path.split("/") if segment]
