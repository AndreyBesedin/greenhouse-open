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

The routes are grouped by what they answer, a module each, with the table
of its routes at its top:

- `system`: whether the API is up, and its version;
- `scenarios`: the scenarios, and each one's manifest, scene, weather,
  CFD geometry and layout;
- `runs`: what a scenario's run holds at a moment, its fields, climate,
  crop and timeline;
- `checkpoints`: a run's checkpoints, made, listed, downloaded and uploaded;
- `playback`: a scenario's run played back against one clock;
- `lab`: the plant lab;
- `builder`: the setup builder, its drafts and its first form.

Each answers its GET routes in `get` and its POST routes in `post`, with
None for a path not its own; `shared` holds what they read requests with
and answer with.
"""

from collections.abc import Callable
from http import HTTPStatus
from typing import Final
from urllib.parse import parse_qs, urlsplit

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes import (
    builder,
    checkpoints,
    lab,
    playback,
    runs,
    scenarios,
    system,
)
from greenhouse_sim.api.routes.shared import Query, error, segments_of
from greenhouse_sim.services.simulator import Simulator

__all__ = ["respond"]

type Getting = Callable[[Simulator, list[str], Query], Response | None]
type Posting = Callable[[Simulator, list[str], Query, bytes], Response | None]

# Each area's GET routes, and its POST routes; a path is any one's at most.
GETS: Final[tuple[Getting, ...]] = (
    system.get,
    scenarios.get,
    runs.get,
    checkpoints.get,
    playback.get,
    lab.get,
    builder.get,
)
POSTS: Final[tuple[Posting, ...]] = (checkpoints.post, playback.post, builder.post)


def respond(simulator: Simulator, method: str, path: str, body: bytes = b"") -> Response:
    """The answer to a request, from `simulator` (decision 0048)."""
    query = parse_qs(urlsplit(path).query)
    segments = segments_of(path)
    if method == "POST":
        for post in POSTS:
            if (answered := post(simulator, segments, query, body)) is not None:
                return answered
        return error(HTTPStatus.METHOD_NOT_ALLOWED, f"{path!r} only answers GET")
    if method != "GET":
        return error(HTTPStatus.METHOD_NOT_ALLOWED, f"{path!r} only answers GET")
    for get in GETS:
        if (answered := get(simulator, segments, query)) is not None:
            return answered
    return error(HTTPStatus.NOT_FOUND, f"nothing at {path!r}")
