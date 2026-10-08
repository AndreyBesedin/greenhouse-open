"""What the local API answers, independent of HTTP.

`respond` maps a method and a path to a status and a JSON-ready body, so the
API can be tested without a socket and the server stays a thin shell.

The routes are only the interface to the simulator's services
(`greenhouse_sim.services`). Each does four things, in order: checks that
the caller may make the request, reads the request into the typed form its
service takes, calls the service, and answers with the result, or with the
status that says what went wrong. Everything else (lookups, rules, case
handling) is the services' (decision 0021). The API answers only on this
machine (decision 0009) and has no users yet, so no route has a right to
check; a route that comes to need one checks it first.

    GET /api/health                       the API is up
    GET /api/version                      simulator and scene schema versions
    GET /api/scenarios                    the registered scenarios, with the
                                          names of their layouts
    GET /api/scenarios/{id}/scene         a scenario's scene before its first day;
                                          ?layout=benches shows another of its
                                          layouts, ?envelope=length:12,spans:3
                                          changes its greenhouse's dimensions,
                                          and ?open=roof_vent_1:0.5,door_1:1 how
                                          far its doors and vents stand open, and
                                          ?set=fan:1,heater:0.5 how hard its
                                          equipment runs
    GET /api/scenarios/{id}/fields        the names of a scenario's fields, and
                                          which is its own airflow
    GET /api/scenarios/{id}/fields/{name} one of a scenario's environment fields:
                                          its greenhouse's air, cell by cell;
                                          both ?layout=open with another of its
                                          layouts, for its CFD solution, and
                                          ?set=fan:1 with its equipment
                                          running and &t=600 that many seconds
                                          into the run, for its climate
    GET /api/scenarios/{id}/cfd/geometry  the boundaries of a scenario's air as
                                          a CFD solver is given them, snapped
                                          to its mesh; changed as for its scene
    GET /api/scenarios/{id}/layout        a scenario's layout, as its file holds
                                          it; ?layout=benches another of them
    GET /api/plants/scene                 the plant lab's scene: a row of tomato
                                          plants from the organ-level model;
                                          ?day=12 on another day of the lab's
                                          run, ?seed=7 drawn from another seed,
                                          ?environment=cool_dim in another of
                                          its environments, &versus=warm_bright
                                          every second plant in another
                                          &act=30:p01:remove_leaf:p01_n02_leaf
                                          schedules an action (repeatable):
                                          remove_leaf, harvest_fruit,
                                          harvest_truss, or lower_stem by a
                                          number of internodes
    GET /api/plants/structure             one of the lab's plants, organ by organ;
                                          ?plant=p07 another plant, and the rest
                                          as for its scene
    GET /api/plants/checks                what is wrong with each of the lab's
                                          plants on a run's day, by the
                                          structure's rules and since the day
                                          before; the run as for its scene
    GET /api/plants/environments          the lab's environments, by name
    GET /api/scenarios/{id}/live          the scenario played live, as Server-Sent
                                          Events (served by `server`, found by
                                          `live_stream`)
    POST /api/scenarios/{id}/live/...     commands for that live run (`control`)
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from typing import Final
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel

from greenhouse_sim.services import cfd, fields, plants, scenarios, system
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.live import InvalidSpeed, LiveCommand, LiveRun, LiveRuns

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None
type Query = dict[str, list[str]]


@dataclass(frozen=True)
class Response:
    status: HTTPStatus
    body: JsonValue


# How each kind of service error is answered; the first that matches.
_REFUSALS: Final = (
    (NotFound, HTTPStatus.NOT_FOUND),
    (InvalidRequest, HTTPStatus.BAD_REQUEST),
)


def respond(method: str, path: str) -> Response:
    if method != "GET":
        return _error(HTTPStatus.METHOD_NOT_ALLOWED, f"{path!r} only answers GET")
    query = parse_qs(urlsplit(path).query)

    match _segments(path):
        case ["api", "health"]:
            return _answer(system.health)
        case ["api", "version"]:
            return _answer(system.version)
        case ["api", "scenarios"]:
            return _answer(scenarios.scenario_summaries)
        case ["api", "plants", "scene"]:
            return _answer(lambda: plants.scene(_lab_run(query)))
        case ["api", "plants", "structure"]:
            plant_id = _last(query, "plant") or plants.LAB_PLANT_ID
            return _answer(lambda: plants.structure(_lab_run(query), plant_id))
        case ["api", "plants", "checks"]:
            return _answer(lambda: plants.checks(_lab_run(query)))
        case ["api", "plants", "environments"]:
            return _answer(
                lambda: {
                    name: e.model_dump(mode="json") for name, e in plants.environments().items()
                }
            )
        case ["api", "scenarios", scenario_id, "scene"]:
            return _answer(lambda: scenarios.initial_scene(scenario_id, _scene_changes(query)))
        case ["api", "scenarios", scenario_id, "fields"]:
            layout = _last(query, "layout")
            return _answer(
                lambda: {
                    "fields": list(fields.field_names(scenario_id, layout)),
                    "configured": fields.configured(scenario_id),
                }
            )
        case ["api", "scenarios", scenario_id, "fields", field_name]:
            layout = _last(query, "layout")
            return _answer(
                lambda: fields.field(
                    scenario_id,
                    field_name,
                    layout,
                    _pairs(query.get("set", []), "set"),
                    _seconds(query),
                )
            )
        case ["api", "scenarios", scenario_id, "cfd", "geometry"]:
            return _answer(lambda: cfd.geometry(scenario_id, _scene_changes(query)))
        case ["api", "scenarios", scenario_id, "layout"]:
            name = _last(query, "layout")
            if name is None:
                return _answer(lambda: scenarios.layout(scenario_id))
            return _answer(lambda: scenarios.layout(scenario_id, name))
        case _:
            return _error(HTTPStatus.NOT_FOUND, f"nothing at {path!r}")


def live_stream(path: str, runs: LiveRuns) -> LiveRun | Response | None:
    """The live run a request for a scenario's stream names, or the refusal
    if it names no scenario; None for any other path."""
    match _segments(path):
        case ["api", "scenarios", scenario_id, "live"]:
            try:
                return runs.run(scenario_id)
            except ServiceError as error:
                return _refusal(error)
        case _:
            return None


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
        case ["api", "scenarios", scenario_id, "live", "speed"]:
            query = parse_qs(url.query)
            return _answer(lambda: runs.set_speed(scenario_id, _multiplier(query)))
        case ["api", "scenarios", scenario_id, "live", command]:
            if command not in LiveCommand:
                return _error(HTTPStatus.NOT_FOUND, f"no live command {command!r}")
            return _answer(lambda: runs.command(scenario_id, LiveCommand(command)))
        case _:
            return None


def _answer(
    call: Callable[[], BaseModel | Sequence[BaseModel] | dict[str, JsonValue]],
) -> Response:
    """The service's result as a response, or its error as a refusal."""
    try:
        result = call()
    except ServiceError as error:
        return _refusal(error)
    body: JsonValue
    if isinstance(result, BaseModel):
        body = result.model_dump(mode="json")
    elif isinstance(result, dict):
        body = result
    else:
        body = [item.model_dump(mode="json") for item in result]
    return Response(HTTPStatus.OK, body)


def _refusal(error: ServiceError) -> Response:
    status = next(status for kind, status in _REFUSALS if isinstance(error, kind))
    return _error(status, error.message)


def _error(status: HTTPStatus, message: str) -> Response:
    return Response(status, {"error": message})


def _scene_changes(query: Query) -> scenarios.SceneChanges:
    """The changes a scene request asks for, as its query writes them."""
    changes: dict[str, object] = {
        "envelope": _pairs(query.get("envelope", []), "envelope"),
        "openings": _pairs(query.get("open", []), "open"),
        "levels": _pairs(query.get("set", []), "set"),
    }
    name = _last(query, "layout")
    if name is not None:
        changes["layout"] = name
    return scenarios.SceneChanges.model_validate(changes)


def _pairs(requests: list[str], name: str) -> dict[str, float]:
    """`name=key:number,key:number` as numbers by key."""
    pairs: dict[str, float] = {}
    for request in ",".join(requests).split(","):
        if not request:
            continue
        key, _, number = request.partition(":")
        try:
            pairs[key] = float(number)
        except ValueError:
            raise InvalidRequest(f"{name} wants key:number pairs, not {request!r}") from None
    return pairs


def _seconds(query: Query) -> float:
    """The moment a query asks for, `t`, in seconds: the start if none."""
    text = _last(query, "t")
    if text is None:
        return 0.0
    try:
        return float(text)
    except ValueError:
        raise InvalidRequest(f"t wants seconds, not {text!r}") from None


def _multiplier(query: Query) -> float:
    """The one speed multiplier a query gives, as a number."""
    values = query.get("multiplier", [])
    if len(values) != 1:
        raise InvalidSpeed()
    try:
        return float(values[0])
    except ValueError:
        raise InvalidSpeed() from None


# A scheduled action's parts: its day, plant, kind and target.
LAB_ACTION_PARTS: Final = ("day", "plant", "action", "organ")


def _lab_run(query: Query) -> plants.LabRun:
    """The plant lab's run a query asks for: day 0, the lab's own seed and
    its reference environment, unless it says."""
    return plants.LabRun(
        day=_whole(query, "day", 0),
        seed=_whole(query, "seed", plants.LAB_SEED),
        environment=_last(query, "environment") or plants.REFERENCE,
        versus=_last(query, "versus"),
        actions=tuple(_lab_action(text) for text in query.get("act", [])),
    )


def _lab_action(text: str) -> plants.LabAction:
    """A scheduled action as a query writes it: `day:plant:action:organ`."""
    parts = text.split(":")
    if len(parts) != len(LAB_ACTION_PARTS) or not parts[0].isdigit():
        raise InvalidRequest(f"act wants day:plant:action:organ, not {text!r}")
    day, plant_id, kind, target = parts
    return plants.LabAction(day=int(day), plant_id=plant_id, kind=kind, target=target)


def _whole(query: Query, name: str, default: int) -> int:
    """A parameter as a whole number, or `default` if the query has none."""
    value = _last(query, name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise InvalidRequest(f"{name} wants a whole number, not {value!r}") from None


def _last(query: Query, name: str) -> str | None:
    """A parameter's last value in a query, if it has one."""
    values = query.get(name)
    return values[-1] if values else None


def _segments(path: str) -> list[str]:
    return [segment for segment in urlsplit(path).path.split("/") if segment]
