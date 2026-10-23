"""The API itself: whether it is up, and the versions of the simulator and
of the scene's schema that it serves.

    GET /api/health                       the API is up
    GET /api/version                      the simulator's version and commit,
                                          and its scene schema's version
"""

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer
from greenhouse_sim.services import system
from greenhouse_sim.services.simulator import Simulator


def get(_simulator: Simulator, segments: list[str], _query: Query) -> Response | None:
    match segments:
        case ["api", "health"]:
            return answer(system.health)
        case ["api", "version"]:
            return answer(system.version)
        case _:
            return None
