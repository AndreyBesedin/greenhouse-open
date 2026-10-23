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
    GET /api/version                      the simulator's version and commit,
                                          and its scene schema's version
    GET /api/scenarios                    the registered scenarios, with the
                                          names of their layouts
    GET /api/scenarios/{id}/manifest      what a scenario's run is made from,
                                          for QA: its manifest's format and
                                          version, its seed, its days and its
                                          models; &weather= as for its climate
    GET /api/scenarios/{id}/scene         a scenario's scene before its first day;
                                          ?layout=propagation shows another of its
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
                                          running, &schedule=60:fan:1,300:fan:0
                                          switching it at those moments,
                                          &daily=64800:heater:1 every day at
                                          that time of day, in place of its
                                          scenario's own, or &daily=none for
                                          none, &targets=3600:heating_day:24
                                          its heating setpoint by day 24 °C
                                          from that moment on, on the minute
                                          (#274),
                                          &open=roof_vent:1 with its vents
                                          open, and &t=600 that many seconds
                                          into the run, to its last day's end,
                                          for its climate, and
                                          &weather=cold_spring_day under a
                                          preset weather, not its own; @80
                                          after its name overrides its
                                          clouds, and ~90 its wind's
                                          direction, for QA
    GET /api/scenarios/{id}/climate/probes what probes at ?probes=3:3.2:0.75,… read
                                          of its climate run every minute up to
                                          &t=600, and of the same run with all
                                          its equipment off; asked as its
                                          climate field is
    GET /api/scenarios/{id}/climate/house  its house's air as one well-mixed
                                          volume every minute up to &t=600,
                                          from the start of that moment's day
                                          or &from=0, and of the same run all
                                          off; asked as its climate field is
    GET /api/scenarios/{id}/climate/glazing its walls' and roof slopes' air,
                                          temperature and heat passed &t=600
                                          seconds into its climate run; asked
                                          as its climate field is
    GET /api/scenarios/{id}/climate/openings what its open doors and vents pass
                                          &t=600 seconds into its climate run,
                                          net and each way; asked as its
                                          climate field is
    GET /api/scenarios/{id}/climate/plants the light on each of its plants &t=600
                                          seconds into a run, its PAR then
                                          and its day's light integral, its
                                          crowns as its crop stands then;
                                          asked as its climate field is
    GET /api/scenarios/{id}/crop          its crop &t=600 seconds into a run,
                                          organ by organ, as a viewer draws
                                          it over its scene, where it grows
                                          one so; asked as its climate field
                                          is
    GET /api/scenarios/{id}/crop/{plant}  one plant of that crop: its
                                          structure, its history, and what
                                          it experienced each day it has
                                          lived; asked as its crop is
    GET /api/scenarios/{id}/climate/observations its run's observation log up to
                                          &t=600, from the start of that
                                          moment's day or &from=0: what its point sensors
                                          observed, whether each is fresh,
                                          and its cameras' frames; asked as
                                          its climate field is; &clean=1 as
                                          clean sensors would have, for QA
    GET /api/scenarios/{id}/climate/equipment its equipment's levels at &t=600,
                                          as its commands set them and its
                                          thermostat, if it has one, runs its
                                          heater, with the thermostat's
                                          setpoint then; asked as its climate
                                          field is
    GET /api/scenarios/{id}/climate/state what each process of its run holds at
                                          &t=600, for QA mode's developer
                                          panel: the clock, the house's air,
                                          the crop's days, the equipment's
                                          and openings' levels and the latest
                                          commands, each sensor's freshness
                                          and each camera's latest frame;
                                          asked as its climate field is
    GET /api/scenarios/{id}/climate/truth what its point sensors truly sampled,
                                          as its log is asked for; for
                                          evaluation and QA only
    GET /api/scenarios/{id}/timeline      every event of its run, by process,
                                          subject and kind, in the order they
                                          happen, up to &t=600 from the start
                                          of that moment's day or &from=0, a
                                          day at most; asked as its climate
                                          field is, though its &open= and
                                          &weather= change none of its events
    GET /api/scenarios/{id}/weather       its site, and the weather outside it &t=600
                                          seconds into a run, with the wind in
                                          the world's axes; &weather=cold_spring_day
                                          under a preset, as for its climate
    GET /api/scenarios/{id}/weather/day   its weather every ten minutes through
                                          its run's first day, or the day of
                                          &t=600
    GET /api/scenarios/{id}/cfd/geometry  the boundaries of a scenario's air as
                                          a CFD solver is given them, snapped
                                          to its mesh; changed as for its scene
    GET /api/scenarios/{id}/layout        a scenario's layout, as its file holds
                                          it; ?layout=propagation another of them
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
    POST /api/scenarios/{id}/checkpoints  a checkpoint of its run at the start
                                          of the day &t=600 lies in: its
                                          house's air and its crop then;
                                          asked as its climate field is
    GET /api/checkpoints                  the checkpoints kept, the earliest
                                          first
    GET /api/checkpoints/{id}             one of them, as JSON to download
    POST /api/checkpoints                 one uploaded, as the request's JSON
                                          body, checked and kept
    GET /api/scenarios/{id}/live          the scenario played live, as Server-Sent
                                          Events (served by `server`, found by
                                          `live_stream`)
    POST /api/scenarios/{id}/live/...     commands for that live run (`control`)
    GET /api/scenarios/{id}/playback      its own run played back against one
                                          clock, which the viewer and a
                                          consumer follow (P10.2): the run,
                                          its layout, its epoch, the clock
    POST /api/scenarios/{id}/playback/start?seconds_per_day=10
                                          started, or played on, at that pace;
                                          &layout=default~heater:-1:0.5 with
                                          that layout, rearranged
    POST /api/scenarios/{id}/playback/play, /pause, /restart (a new epoch)
    POST /api/scenarios/{id}/playback/restart?layout=default~heater:-1:0.5
                                          started over with another layout:
                                          its run, from its start (#271)
    POST /api/scenarios/{id}/playback/pace?seconds_per_day=5
    POST /api/scenarios/{id}/playback/targets?targets=heating_day:24,heating_night:18
                                          its run's targets changed from its
                                          clock's next minute on, in the same
                                          run and epoch (#274, decision 0043)
    GET /api/drafts                       the installations' drafts kept, each
                                          at its latest revision (P12.1,
                                          decision 0051)
    GET /api/drafts/{id}                  one, its installation and what stops
                                          it running; ?revision=2 an earlier
                                          revision
    GET /api/drafts/{id}/revisions        its revisions, the first first
    POST /api/drafts/{id}/save?on=3       an installation's file, the body,
                                          saved as its next revision, made on
                                          revision 3; without on, a new draft
    POST /api/drafts/{id}/revert?revision=1&on=3
                                          an earlier revision saved again as
                                          its latest
    POST /api/drafts/{id}/delete?on=3     forgotten with its revisions
    POST /api/drafts/{id}/run?revision=2  run as a scenario of its own, with
                                          its period, site, seed and weather
                                          as the body gives them, registered
                                          and listed with the others

    GET /api/scenarios/{id}/installation  a scenario's house as an
                                          installation, assessed, for the
                                          builder to copy (P12.2)
    POST /api/builder/basic               a first draft from the builder's
                                          first form's values, the body,
                                          assessed (P12.2)
    POST /api/builder/assess              an installation's file, the body,
                                          read and assessed as it stands
    POST /api/builder/scene               the house an installation's file,
                                          the body, describes, as a scene

A change to a draft made on a revision that is no longer its latest is
refused as a conflict (409), as is a draft's run under a scenario's name
already taken.
"""

import json
from collections.abc import Callable, Sequence
from http import HTTPStatus
from typing import Final
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel

from greenhouse_sim.api.responses import JsonValue, Response
from greenhouse_sim.services import (
    builder,
    cfd,
    checkpoints,
    climate_readings,
    crop,
    drafts,
    fields,
    plants,
    playback,
    run_state,
    scenarios,
    sensors,
    system,
    timeline,
    weather,
)
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.live import InvalidSpeed, LiveCommand, LiveRun, LiveRuns
from greenhouse_sim.services.playback import PlaybackCommand
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

type Query = dict[str, list[str]]


# The largest revision a query may name: the largest whole number a draft's
# store keeps (SQLite's).
MOST_REVISION: Final = 2**63 - 1

# How each kind of service error is answered; the first that matches.
_REFUSALS: Final = (
    (NotFound, HTTPStatus.NOT_FOUND),
    (InvalidRequest, HTTPStatus.BAD_REQUEST),
    (Conflict, HTTPStatus.CONFLICT),
)


def respond(simulator: Simulator, method: str, path: str, body: bytes = b"") -> Response:
    """The answer to a request, from `simulator` (decision 0048)."""
    query = parse_qs(urlsplit(path).query)
    if method == "POST":
        return _posted(simulator, path, query, body)
    if method != "GET":
        return _error(HTTPStatus.METHOD_NOT_ALLOWED, f"{path!r} only answers GET")

    match _segments(path):
        case ["api", "health"]:
            return _answer(system.health)
        case ["api", "version"]:
            return _answer(system.version)
        case ["api", "scenarios"]:
            return _answer(lambda: scenarios.scenario_summaries(simulator.catalogue))
        case ["api", "scenarios", scenario_id, "installation"]:
            return _answer(lambda: builder.scenario_house(simulator.catalogue, scenario_id))
        case ["api", "drafts"]:
            return _answer(lambda: drafts.drafts(simulator))
        case ["api", "drafts", draft_id]:
            return _answer(lambda: drafts.draft(simulator, draft_id, _revision(query, "revision")))
        case ["api", "drafts", draft_id, "revisions"]:
            return _answer(lambda: drafts.revisions(simulator, draft_id))
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
        case ["api", "scenarios", scenario_id, "playback"]:
            return _answer(lambda: playback.state(simulator, scenario_id))
        case ["api", "scenarios", scenario_id, "manifest"]:
            return _answer(
                lambda: scenarios.run_manifest(
                    simulator.catalogue, scenario_id, _last(query, "weather")
                )
            )
        case ["api", "scenarios", scenario_id, "scene"]:
            return _answer(
                lambda: scenarios.initial_scene(
                    simulator.catalogue, scenario_id, _scene_changes(query)
                )
            )
        case ["api", "scenarios", scenario_id, "fields"]:
            return _answer(
                lambda: fields.offered_fields(simulator, scenario_id, _last(query, "layout"))
            )
        case ["api", "scenarios", scenario_id, "fields", field_name]:
            return _answer(
                lambda: fields.field(
                    simulator, _run(scenario_id, query), field_name, _seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "probes"]:
            return _answer(
                lambda: climate_readings.climate_probes(
                    simulator,
                    _run(scenario_id, query),
                    _points(query.get("probes", [])),
                    _seconds(query),
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "house"]:
            return _answer(
                lambda: climate_readings.house_air(
                    simulator, _run(scenario_id, query), _seconds(query), _since(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "glazing"]:
            return _answer(
                lambda: climate_readings.glazing(
                    simulator, _run(scenario_id, query), _seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "openings"]:
            return _answer(
                lambda: climate_readings.openings(
                    simulator, _run(scenario_id, query), _seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "plants"]:
            return _answer(
                lambda: crop.plants_light(simulator, _run(scenario_id, query), _seconds(query))
            )
        case ["api", "scenarios", scenario_id, "crop"]:
            return _answer(
                lambda: crop.crop_scene(simulator, _run(scenario_id, query), _seconds(query))
            )
        case ["api", "scenarios", scenario_id, "crop", plant_id]:
            return _answer(
                lambda: crop.crop_plant(
                    simulator, _run(scenario_id, query), plant_id, _seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "observations"]:
            return _answer(
                lambda: sensors.observations(
                    simulator,
                    _run(scenario_id, query),
                    _seconds(query),
                    clean=_last(query, "clean") == "1",
                    from_s=_since(query),
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "equipment"]:
            return _answer(
                lambda: climate_readings.equipment_at(
                    simulator, _run(scenario_id, query), _seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "state"]:
            return _answer(
                lambda: run_state.run_state(simulator, _run(scenario_id, query), _seconds(query))
            )
        case ["api", "scenarios", scenario_id, "climate", "truth"]:
            return _answer(
                lambda: sensors.truth(
                    simulator, _run(scenario_id, query), _seconds(query), _since(query)
                )
            )
        case ["api", "scenarios", scenario_id, "timeline"]:
            return _answer(
                lambda: timeline.timeline(
                    simulator.catalogue, _run(scenario_id, query), _seconds(query), _since(query)
                )
            )
        case ["api", "scenarios", scenario_id, "weather"]:
            return _answer(
                lambda: weather.at_a_moment(
                    simulator.catalogue, scenario_id, _seconds(query), _last(query, "weather")
                )
            )
        case ["api", "scenarios", scenario_id, "weather", "day"]:
            return _answer(
                lambda: weather.through_the_day(
                    simulator.catalogue, scenario_id, _last(query, "weather"), _seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "cfd", "geometry"]:
            return _answer(
                lambda: cfd.geometry(simulator.catalogue, scenario_id, _scene_changes(query))
            )
        case ["api", "checkpoints"]:
            return _answer(lambda: checkpoints.checkpoints(simulator))
        case ["api", "checkpoints", checkpoint_id]:
            return _answer(lambda: checkpoints.checkpoint(simulator, checkpoint_id))
        case ["api", "scenarios", scenario_id, "layout"]:
            name = _last(query, "layout")
            if name is None:
                return _answer(lambda: scenarios.layout(simulator.catalogue, scenario_id))
            return _answer(lambda: scenarios.layout(simulator.catalogue, scenario_id, name))
        case _:
            return _error(HTTPStatus.NOT_FOUND, f"nothing at {path!r}")


def _posted(simulator: Simulator, path: str, query: Query, body: bytes) -> Response:
    """What a POST request makes: a checkpoint of a scenario's run, asked for
    as its climate field is, or one uploaded as the request's JSON body."""
    match _segments(path):
        case ["api", "scenarios", scenario_id, "checkpoints"]:
            return _answer(
                lambda: checkpoints.save_checkpoint(
                    simulator, _run(scenario_id, query), _seconds(query)
                )
            )
        case ["api", "checkpoints"]:
            return _answer(lambda: checkpoints.upload_checkpoint(simulator, _json(body)))
        case ["api", "builder", "basic"]:
            return _answer(lambda: builder.basic(_json(body)))
        case ["api", "builder", "assess"]:
            return _answer(lambda: builder.assess(_text(body)))
        case ["api", "builder", "scene"]:
            return _answer(lambda: builder.scene(_text(body)))
        case ["api", "drafts", draft_id, "save"]:
            return _answer(
                lambda: drafts.save(simulator, draft_id, _text(body), _revision(query, "on"))
            )
        case ["api", "drafts", draft_id, "revert"]:
            return _answer(
                lambda: drafts.revert(
                    simulator, draft_id, _named(query, "revision"), _named(query, "on")
                )
            )
        case ["api", "drafts", draft_id, "delete"]:
            return _answer(lambda: drafts.delete(simulator, draft_id, _named(query, "on")))
        case ["api", "drafts", draft_id, "run"]:
            return _answer(
                lambda: drafts.run(simulator, draft_id, _revision(query, "revision"), _json(body))
            )
        case ["api", "scenarios", scenario_id, "playback", "start"]:
            layout = _last(query, "layout")
            return _answer(
                lambda: playback.start(simulator, scenario_id, _pace(query), layout=layout)
            )
        case ["api", "scenarios", scenario_id, "playback", "targets"]:
            return _answer(
                lambda: playback.set_targets(
                    simulator, scenario_id, _pairs(query.get("targets", []), "targets")
                )
            )
        case ["api", "scenarios", scenario_id, "playback", "pace"]:
            return _answer(lambda: playback.set_pace(simulator, scenario_id, _pace(query) or 0.0))
        case ["api", "scenarios", scenario_id, "playback", action]:
            if action not in PlaybackCommand:
                return _error(HTTPStatus.NOT_FOUND, f"no playback command {action!r}")
            layout = _last(query, "layout")
            return _answer(
                lambda: playback.command(simulator, scenario_id, PlaybackCommand(action), layout)
            )
        case _:
            return _error(HTTPStatus.METHOD_NOT_ALLOWED, f"{path!r} only answers GET")


def _json(body: bytes) -> JsonValue:
    """A request's body, read as JSON: standard JSON, whose numbers are all
    finite, not Python's, which reads `NaN` and `Infinity` too."""
    try:
        parsed: JsonValue = json.loads(body, parse_constant=_not_a_number)
    except ValueError:
        raise InvalidRequest("the body is not JSON") from None
    return parsed


def _text(body: bytes) -> str:
    """A request's body, as the UTF-8 text it is sent in."""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidRequest("the body is not UTF-8 text") from None


def _not_a_number(name: str) -> JsonValue:
    raise InvalidRequest(f"the body holds {name}, which JSON has no number for")


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


def _run(scenario_id: str, query: Query) -> RunRequest:
    """The run a query asks for of a scenario, read once: `layout=`,
    `weather=`, `set=`, `open=`, `schedule=`, `daily=` and `targets=`."""
    levels = _pairs(query.get("set", []), "set")
    openings = _pairs(query.get("open", []), "open")
    commands = tuple(_commands(query.get("schedule", [])))
    daily = _daily(query)
    targets = tuple(_commands(query.get("targets", []), "targets", "seconds:target:celsius"))
    return RunRequest(
        scenario_id=scenario_id,
        layout=_last(query, "layout"),
        weather=_last(query, "weather"),
        levels=levels,
        openings=openings,
        commands=commands,
        daily=None if daily is None else tuple(daily),
        targets=targets,
    )


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


def _commands(
    requests: list[str], name: str = "schedule", shape: str = "seconds:actuator:level"
) -> list[tuple[float, str, float]]:
    """`schedule=seconds:actuator:level,…` as commands, in the order given;
    or `daily=`, at those seconds into each day; or `targets=` (#274), each
    a target changed to a value, in °C, from those seconds on."""
    commands = []
    for request in ",".join(requests).split(","):
        if not request:
            continue
        time, _, rest = request.partition(":")
        actuator, _, level = rest.partition(":")
        try:
            commands.append((float(time), actuator, float(level)))
        except ValueError:
            raise InvalidRequest(f"{name} wants {shape} commands, not {request!r}") from None
    return commands


def _daily(query: Query) -> list[tuple[float, str, float]] | None:
    """`daily=seconds:actuator:level,…`, a run's daily commands in place of
    its scenario's; `daily=none` for none; or None if the query gives none,
    for its scenario's own."""
    requests = query.get("daily")
    if requests is None:
        return None
    if requests == [NO_DAILY_COMMANDS]:
        return []
    return _commands(requests, "daily")


def _points(requests: list[str]) -> list[tuple[float, float, float]]:
    """`probes=x:y:z,…` as points, in the order given."""
    points = []
    for request in ",".join(requests).split(","):
        if not request:
            continue
        try:
            x, y, z = (float(part) for part in request.split(":"))
        except ValueError:
            raise InvalidRequest(f"probes wants x:y:z points, not {request!r}") from None
        points.append((x, y, z))
    return points


def _seconds(query: Query, name: str = "t") -> float:
    """The moment a query asks for, `t`, in seconds: the start if none."""
    text = _last(query, name)
    if text is None:
        return 0.0
    try:
        return float(text)
    except ValueError:
        raise InvalidRequest(f"{name} wants seconds, not {text!r}") from None


def _since(query: Query) -> float | None:
    """Where a series a query asks for begins, `from`, in seconds; None if
    it does not say, for the service's own default."""
    return None if _last(query, "from") is None else _seconds(query, "from")


def _multiplier(query: Query) -> float:
    """The one speed multiplier a query gives, as a number."""
    values = query.get("multiplier", [])
    if len(values) != 1:
        raise InvalidSpeed()
    try:
        return float(values[0])
    except ValueError:
        raise InvalidSpeed() from None


# How a query asks for a run without daily commands, its scenario's too.
NO_DAILY_COMMANDS: Final = "none"
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


def _pace(query: Query) -> float | None:
    """The real seconds a playback plays a simulated day in, if the query
    gives them."""
    given = _last(query, "seconds_per_day")
    if given is None:
        return None
    try:
        return float(given)
    except ValueError:
        raise InvalidRequest(f"seconds_per_day is a number, not {given!r}") from None


def _revision(query: Query, name: str) -> int | None:
    """The revision a query names by `name`, a whole number from 1; None if
    it names none."""
    text = _last(query, name)
    if text is None:
        return None
    # Its digits counted before they are read: a number too long to read,
    # or to keep, is refused as any other.
    whole = text.isascii() and text.isdigit() and len(text) <= len(str(MOST_REVISION))
    if not whole or not 1 <= int(text) <= MOST_REVISION:
        raise InvalidRequest(
            f"{name} is a revision, a whole number from 1 to {MOST_REVISION}, not {text!r}"
        )
    return int(text)


def _named(query: Query, name: str) -> int:
    """The revision a query must name by `name`."""
    revision = _revision(query, name)
    if revision is None:
        raise InvalidRequest(f"the request names no revision as {name}")
    return revision


def _last(query: Query, name: str) -> str | None:
    """A parameter's last value in a query, if it has one."""
    values = query.get(name)
    return values[-1] if values else None


def _segments(path: str) -> list[str]:
    return [segment for segment in urlsplit(path).path.split("/") if segment]
