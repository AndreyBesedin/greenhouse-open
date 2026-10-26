"""A scenario's own run played back against one clock, which the viewer and
a consumer follow (P10.2).

    GET /api/scenarios/{id}/playback      its own run played back against one
                                          clock, which the viewer and a
                                          consumer follow (P10.2): the run,
                                          its layout, its epoch, the clock
    POST /api/scenarios/{id}/playback/start?seconds_per_day=10
                                          started, or played on, at that pace;
                                          &layout=default~heater:-1:0.5 with
                                          that layout, rearranged; &hold=true
                                          held at its start, for a plan given
                                          before its clock moves (P13.7)
    POST /api/scenarios/{id}/playback/play, /pause, /restart (a new epoch)
    POST /api/scenarios/{id}/playback/restart?layout=default~heater:-1:0.5
                                          started over with another layout:
                                          its run, from its start (#271)
    POST /api/scenarios/{id}/playback/pace?seconds_per_day=5
    POST /api/scenarios/{id}/playback/targets?targets=heating_day:24,heating_night:18
                                          its run's targets changed from its
                                          clock's next minute on, in the same
                                          run and epoch (#274, decision 0043):
                                          deprecated, the next revision of its
                                          plan `targets`, as the gateway's
                                          plans route gives one (P13.7)
"""

from http import HTTPStatus

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer, error, last, pairs
from greenhouse_sim.services import playback
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.playback import PlaybackCommand
from greenhouse_sim.services.simulator import Simulator


def get(simulator: Simulator, segments: list[str], _query: Query) -> Response | None:
    match segments:
        case ["api", "scenarios", scenario_id, "playback"]:
            return answer(lambda: playback.state(simulator, scenario_id))
        case _:
            return None


def post(simulator: Simulator, segments: list[str], query: Query, _body: bytes) -> Response | None:
    match segments:
        case ["api", "scenarios", scenario_id, "playback", "start"]:
            layout = last(query, "layout")
            return answer(
                lambda: playback.start(
                    simulator, scenario_id, _pace(query), layout=layout, hold=_held(query)
                )
            )
        case ["api", "scenarios", scenario_id, "playback", "targets"]:
            return answer(
                lambda: playback.set_targets(
                    simulator, scenario_id, pairs(query.get("targets", []), "targets")
                )
            )
        case ["api", "scenarios", scenario_id, "playback", "pace"]:
            return answer(lambda: playback.set_pace(simulator, scenario_id, _pace(query) or 0.0))
        case ["api", "scenarios", scenario_id, "playback", action]:
            if action not in PlaybackCommand:
                return error(HTTPStatus.NOT_FOUND, f"no playback command {action!r}")
            layout = last(query, "layout")
            return answer(
                lambda: playback.command(simulator, scenario_id, PlaybackCommand(action), layout)
            )
        case _:
            return None


def _held(query: Query) -> bool:
    """Whether a playback started is held at its start: `hold=true`."""
    given = last(query, "hold")
    if given not in {None, "true", "false"}:
        raise InvalidRequest(f"hold is true or false, not {given!r}")
    return given == "true"


def _pace(query: Query) -> float | None:
    """The real seconds a playback plays a simulated day in, if the query
    gives them."""
    given = last(query, "seconds_per_day")
    if given is None:
        return None
    try:
        return float(given)
    except ValueError:
        raise InvalidRequest(f"seconds_per_day is a number, not {given!r}") from None
