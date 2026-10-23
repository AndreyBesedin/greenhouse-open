"""A scenario played live, day by day, and the commands its viewers give it.
The server streams it (`server`), finding the run with `live_stream`, and
passes its commands to `control`.

    GET /api/scenarios/{id}/live          the scenario played live, as Server-Sent
                                          Events
    POST /api/scenarios/{id}/live/play    play on from the current day
    POST /api/scenarios/{id}/live/pause   hold the current day
    POST /api/scenarios/{id}/live/step    one simulated day on
    POST /api/scenarios/{id}/live/reset   back to before day one
    POST /api/scenarios/{id}/live/speed?multiplier=2
                                          play faster or slower
"""

from http import HTTPStatus
from urllib.parse import parse_qs, urlsplit

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer, error, refusal, segments_of
from greenhouse_sim.services.errors import ServiceError
from greenhouse_sim.services.live import InvalidSpeed, LiveCommand, LiveRun, LiveRuns


def live_stream(path: str, runs: LiveRuns) -> LiveRun | Response | None:
    """The live run a request for a scenario's stream names, or the refusal
    if it names no scenario; None for any other path."""
    match segments_of(path):
        case ["api", "scenarios", scenario_id, "live"]:
            try:
                return runs.run(scenario_id)
            except ServiceError as refused:
                return refusal(refused)
        case _:
            return None


def control(path: str, runs: LiveRuns) -> Response | None:
    """Applies a command to a scenario's live run, if `path` names one. The
    answer is the run's new state without its scene, which reaches every
    viewer on the stream."""
    url = urlsplit(path)
    match segments_of(url.path):
        case ["api", "scenarios", scenario_id, "live", "speed"]:
            query = parse_qs(url.query)
            return answer(lambda: runs.set_speed(scenario_id, _multiplier(query)))
        case ["api", "scenarios", scenario_id, "live", command]:
            if command not in LiveCommand:
                return error(HTTPStatus.NOT_FOUND, f"no live command {command!r}")
            return answer(lambda: runs.command(scenario_id, LiveCommand(command)))
        case _:
            return None


def _multiplier(query: Query) -> float:
    """The one speed multiplier a query gives, as a number."""
    values = query.get("multiplier", [])
    if len(values) != 1:
        raise InvalidSpeed()
    try:
        return float(values[0])
    except ValueError:
        raise InvalidSpeed() from None
