"""A run's checkpoints: made from a run asked for as its climate field is,
kept, listed, downloaded and uploaded.

    POST /api/scenarios/{id}/checkpoints  a checkpoint of its run at the start
                                          of the day &t=600 lies in: its
                                          house's air and its crop then;
                                          asked as its climate field is
    GET /api/checkpoints                  the checkpoints kept, the earliest
                                          first
    GET /api/checkpoints/{id}             one of them, as JSON to download
    POST /api/checkpoints                 one uploaded, as the request's JSON
                                          body, checked and kept
"""

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.runs import run_request
from greenhouse_sim.api.routes.shared import Query, answer, json_body, seconds
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.simulator import Simulator


def get(simulator: Simulator, segments: list[str], _query: Query) -> Response | None:
    match segments:
        case ["api", "checkpoints"]:
            return answer(lambda: checkpoints.checkpoints(simulator))
        case ["api", "checkpoints", checkpoint_id]:
            return answer(lambda: checkpoints.checkpoint(simulator, checkpoint_id))
        case _:
            return None


def post(simulator: Simulator, segments: list[str], query: Query, body: bytes) -> Response | None:
    match segments:
        case ["api", "scenarios", scenario_id, "checkpoints"]:
            return answer(
                lambda: checkpoints.save_checkpoint(
                    simulator, run_request(scenario_id, query), seconds(query)
                )
            )
        case ["api", "checkpoints"]:
            return answer(lambda: checkpoints.upload_checkpoint(simulator, json_body(body)))
        case _:
            return None
