"""The runs kept in the run store, and the positions a viewer takes over
them (P17.4, decision 0065).

    GET /api/runs                         every stored run, the newest started
                                          first, as a landing page lists them
    GET /api/scenarios/{id}/runs          a scenario's stored runs, by run and
                                          epoch: seed, layout, status, how far
                                          each is committed, when it was
                                          started, and its size
    GET /api/runs/{run}/epochs/{n}        one stored epoch, as that list shows it
    GET /api/runs/{run}/epochs/{n}/observations|events|outcomes?after=&limit=&t=
                                          its records after a cursor that were
                                          delivered by t seconds into the run,
                                          by default its frontier
    POST /api/scenarios/{id}/runs?seed=7&layout=default&seconds_per_day=10
                                          a run asked for: an epoch started in
                                          the store, queued, and executed by a
                                          worker when one is free, as fast as it
                                          goes or at that pace; the epoch as the
                                          list shows it. Several at once, of one
                                          scenario or of many
    POST /api/runs/{run}/epochs/{n}/stop  an epoch waiting for a worker or being
                                          executed, ended: interrupted, with what
                                          it had committed
    POST /api/runs/{run}/epochs/{n}/positions?seconds_per_day=10
                                          a position at the epoch's start
    GET /api/positions/{id}               where it stands: the moment, whether
                                          it plays or follows, the frontier
    POST /api/runs/{run}/epochs/{n}/delete
                                          removes a stored epoch that is not
                                          being computed, and its positions;
                                          its number is not used again
    POST /api/positions/{id}/play, /pause, /follow, /close
    POST /api/positions/{id}/pace?seconds_per_day=5
    POST /api/positions/{id}/seek?t=3600  to a moment from the start to the
                                          epoch's frontier, not past it
    GET /api/positions/{id}/observations|events|outcomes?after=&limit=
                                          the records its epoch delivered by
                                          the position's moment

A position is the viewer's place over an epoch, not the epoch's clock: moving
it changes nothing a consumer reads.
"""

from pydantic import BaseModel

from greenhouse_sim.api.responses import JsonValue, Response
from greenhouse_sim.api.routes.shared import Query, answer, last, pace, seconds, seed, whole
from greenhouse_sim.services import runs_kept, scheduler
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.simulator import Simulator

KINDS = ("observations", "events", "outcomes")


def get(simulator: Simulator, segments: list[str], query: Query) -> Response | None:
    match segments:
        case ["api", "runs"]:
            return answer(lambda: runs_kept.all_runs(simulator))
        case ["api", "scenarios", scenario_id, "runs"]:
            return answer(lambda: runs_kept.runs_of(simulator, scenario_id))
        case ["api", "runs", run_id, "epochs", number]:
            return answer(lambda: runs_kept.epoch_of(simulator, run_id, _epoch(number)))
        case ["api", "runs", run_id, "epochs", number, kind] if kind in KINDS:
            return answer(lambda: _epoch_records(simulator, run_id, number, kind, query))
        case ["api", "positions", position_id]:
            return answer(lambda: runs_kept.position(simulator, position_id))
        case ["api", "positions", position_id, kind] if kind in KINDS:
            return answer(lambda: _position_records(simulator, position_id, kind, query))
        case _:
            return None


def post(simulator: Simulator, segments: list[str], query: Query, _body: bytes) -> Response | None:
    match segments:
        case ["api", "scenarios", scenario_id, "runs"]:
            return answer(
                lambda: scheduler.start(
                    simulator,
                    scenario_id,
                    layout=last(query, "layout"),
                    seed=seed(query),
                    seconds_per_day=pace(query),
                )
            )
        case ["api", "runs", run_id, "epochs", number, "stop"]:
            return answer(lambda: scheduler.cancel(simulator, run_id, _epoch(number)))
        case ["api", "runs", run_id, "epochs", number, "delete"]:
            return answer(lambda: runs_kept.delete_epoch(simulator, run_id, _epoch(number)))
        case ["api", "runs", run_id, "epochs", number, "positions"]:
            return answer(
                lambda: runs_kept.open_position(simulator, run_id, _epoch(number), pace(query))
            )
        case ["api", "positions", position_id, "seek"]:
            return answer(lambda: runs_kept.seek(simulator, position_id, _moment(query)))
        case ["api", "positions", position_id, "pace"]:
            return answer(lambda: runs_kept.set_pace(simulator, position_id, _required_pace(query)))
        case ["api", "positions", position_id, "close"]:
            return answer(lambda: _closed(simulator, position_id))
        case ["api", "positions", position_id, action] if action in ACTIONS:
            return answer(lambda: ACTIONS[action](simulator, position_id))
        case _:
            return None


ACTIONS = {"play": runs_kept.play, "pause": runs_kept.pause, "follow": runs_kept.follow}


def _epoch(text: str) -> int:
    if not text.isascii() or not text.isdigit():
        raise InvalidRequest(f"an epoch is a whole number, 0 or more, not {text!r}")
    return int(text)


def _moment(query: Query) -> float:
    if last(query, "t") is None:
        raise InvalidRequest("seek wants t, the seconds into the run to move to")
    return seconds(query)


def _required_pace(query: Query) -> float:
    given = pace(query)
    if given is None:
        raise InvalidRequest("pace wants seconds_per_day")
    return given


def _closed(simulator: Simulator, position_id: str) -> dict[str, JsonValue]:
    runs_kept.close(simulator, position_id)
    return {"closed": position_id}


def _count(query: Query, name: str) -> int | None:
    """A cursor or a limit the query gives, for the service to check, or none."""
    return None if last(query, name) is None else whole(query, name, 0)


def _at(query: Query) -> float | None:
    return None if last(query, "t") is None else seconds(query)


def _epoch_records(
    simulator: Simulator, run_id: str, number: str, kind: str, query: Query
) -> BaseModel:
    after, limit = _count(query, "after"), _count(query, "limit")
    reads = {
        "observations": runs_kept.epoch_observations,
        "events": runs_kept.epoch_events,
        "outcomes": runs_kept.epoch_outcomes,
    }
    return reads[kind](simulator, run_id, _epoch(number), after=after, limit=limit, at_s=_at(query))


def _position_records(simulator: Simulator, position_id: str, kind: str, query: Query) -> BaseModel:
    after, limit = _count(query, "after"), _count(query, "limit")
    reads = {
        "observations": runs_kept.position_observations,
        "events": runs_kept.position_events,
        "outcomes": runs_kept.position_outcomes,
    }
    return reads[kind](simulator, position_id, after, limit)
