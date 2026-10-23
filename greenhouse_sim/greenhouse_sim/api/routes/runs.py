"""What a scenario's run holds at a moment: its fields, its climate, its
crop and its timeline, each of the run a query asks for (`run_request`).

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
"""

from typing import Final

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer, last, pairs, seconds, since
from greenhouse_sim.services import (
    climate_readings,
    crop,
    fields,
    run_state,
    sensors,
    timeline,
)
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.simulator import Simulator

# How a query asks for a run without daily commands, its scenario's too.
NO_DAILY_COMMANDS: Final = "none"


def get(simulator: Simulator, segments: list[str], query: Query) -> Response | None:
    match segments:
        case ["api", "scenarios", scenario_id, "fields"]:
            return answer(
                lambda: fields.offered_fields(simulator, scenario_id, last(query, "layout"))
            )
        case ["api", "scenarios", scenario_id, "fields", field_name]:
            return answer(
                lambda: fields.field(
                    simulator, run_request(scenario_id, query), field_name, seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "probes"]:
            return answer(
                lambda: climate_readings.climate_probes(
                    simulator,
                    run_request(scenario_id, query),
                    _points(query.get("probes", [])),
                    seconds(query),
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "house"]:
            return answer(
                lambda: climate_readings.house_air(
                    simulator, run_request(scenario_id, query), seconds(query), since(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "glazing"]:
            return answer(
                lambda: climate_readings.glazing(
                    simulator, run_request(scenario_id, query), seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "openings"]:
            return answer(
                lambda: climate_readings.openings(
                    simulator, run_request(scenario_id, query), seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "plants"]:
            return answer(
                lambda: crop.plants_light(
                    simulator, run_request(scenario_id, query), seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "crop"]:
            return answer(
                lambda: crop.crop_scene(simulator, run_request(scenario_id, query), seconds(query))
            )
        case ["api", "scenarios", scenario_id, "crop", plant_id]:
            return answer(
                lambda: crop.crop_plant(
                    simulator, run_request(scenario_id, query), plant_id, seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "observations"]:
            return answer(
                lambda: sensors.observations(
                    simulator,
                    run_request(scenario_id, query),
                    seconds(query),
                    clean=last(query, "clean") == "1",
                    from_s=since(query),
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "equipment"]:
            return answer(
                lambda: climate_readings.equipment_at(
                    simulator, run_request(scenario_id, query), seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "state"]:
            return answer(
                lambda: run_state.run_state(
                    simulator, run_request(scenario_id, query), seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "climate", "truth"]:
            return answer(
                lambda: sensors.truth(
                    simulator, run_request(scenario_id, query), seconds(query), since(query)
                )
            )
        case ["api", "scenarios", scenario_id, "timeline"]:
            return answer(
                lambda: timeline.timeline(
                    simulator.catalogue,
                    run_request(scenario_id, query),
                    seconds(query),
                    since(query),
                )
            )
        case _:
            return None


def run_request(scenario_id: str, query: Query) -> RunRequest:
    """The run a query asks for of a scenario, read once: `layout=`,
    `weather=`, where it starts from (`set=`, `open=`), and its plan
    (`schedule=`, `daily=`, `targets=`), as written; the run checks it."""
    levels = pairs(query.get("set", []), "set")
    openings = pairs(query.get("open", []), "open")
    plan = RunPlan.requested(
        commands=_commands(query.get("schedule", [])),
        daily=_daily(query),
        targets=_commands(query.get("targets", []), "targets", "seconds:target:celsius"),
    )
    return RunRequest(
        scenario_id=scenario_id,
        layout=last(query, "layout"),
        weather=last(query, "weather"),
        levels=levels,
        openings=openings,
        plan=plan,
    )


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
