"""The gateway's routes (P13.7, decision 0046): a played-back run's plans
given, revised, cancelled and read under `/actuation/v1`, as the local
operator; the playback's targets route an alias of a revision of its plan
`targets`; and what is not a request refused before it reaches the
gateway."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import timedelta
from http import HTTPStatus
from typing import Any, Final

import pytest
from greenhouse_protocol.actions import ActionKind
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.contracts.gateway import PlanState, Receipt
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import ActionState

from greenhouse_sim.api.actuation import actuation_respond
from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes import respond
from greenhouse_sim.api.server import create_server
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services.climate_runs import checked_actions
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.gateway import LOCAL_OPERATOR, run_items
from greenhouse_sim.services.playback import PLAN_OCCURRENCES, TARGETS_PLAN, Playback
from greenhouse_sim.services.runs import RunPlan
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "reference_greenhouse"
CONFIG: Final = scenario(PACKAGED, SCENARIO)
START: Final = run_start(PACKAGED, SCENARIO)
HOUR: Final = timedelta(hours=1)
VENT: Final = sorted(run_items(CONFIG).devices)[0]
ME: Final = LOCAL_OPERATOR.model_dump(mode="json")


class _Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def played() -> Iterator[tuple[Simulator, Playback]]:
    """A simulator playing the scenario's run back, held at its start: no
    day worked out, which the gateway's routes do not need."""
    with Simulator() as simulator:
        found = simulator.playbacks.made_once(
            SCENARIO, lambda _: Playback(simulator, SCENARIO, seconds_per_day=24.0, clock=_Clock())
        )
        yield simulator, found


def _level(action_id: str, at: timedelta, level: float = 1.0, **fields: Any) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "action": {"kind": "set_level", "device_id": VENT, "level": level},
        "timing": {"kind": "at", "at": (START + at).isoformat()},
        "proposed_by": ME,
        **fields,
    }


def _target(action_id: str, at: timedelta) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "action": {"kind": "set_target", "target": "heating_night", "value_c": 17.0},
        "timing": {"kind": "at", "at": (START + at).isoformat()},
        "proposed_by": ME,
    }


def _plan(found: Playback, *actions: dict[str, Any], revision: int = 1, **fields: Any) -> bytes:
    plan = {
        "plan_id": "p",
        "run_id": found.run_id,
        "epoch": found.state().epoch,
        "revision": revision,
        "actions": list(actions),
    }
    return json.dumps(plan | fields).encode()


def _call(simulator: Simulator, method: str, path: str, body: bytes = b"") -> Response:
    answered = actuation_respond(simulator, method, f"/actuation/v1{path}", body)
    assert answered is not None
    return answered


def _receipt(answered: Response) -> Receipt:
    assert answered.status == HTTPStatus.OK, answered.body
    return Receipt.model_validate(answered.body)


def _listed(simulator: Simulator, run_id: str, query: str = "") -> list[str]:
    answered = _call(simulator, "GET", f"/runs/{run_id}/actions{query}")
    assert answered.status == HTTPStatus.OK, answered.body
    assert isinstance(answered.body, list)
    return [str(ActionState.model_validate(each).ref) for each in answered.body]


def test_a_plan_given_is_read_back_and_its_actions_listed(
    played: tuple[Simulator, Playback],
) -> None:
    simulator, found = played
    run_id = found.run_id
    plan = _plan(
        found, _level("open", 6 * HOUR), _target("warm", 7 * HOUR), _level("shut", 8 * HOUR, 0.0)
    )

    receipt = _receipt(_call(simulator, "POST", f"/runs/{run_id}/plans", plan))
    state = PlanState.model_validate(_call(simulator, "GET", f"/runs/{run_id}/plans/p").body)

    assert (receipt.accepted, receipt.refused) == (True, ())
    assert (state.plan.revision, state.owner) == (1, LOCAL_OPERATOR)
    assert _listed(simulator, run_id) == ["open", "warm", "shut"]
    assert _listed(simulator, run_id, "?kind=set_target") == ["warm"]
    assert _listed(simulator, run_id, "?kind=set_level,set_target&plan=p") == [
        "open",
        "warm",
        "shut",
    ]
    assert _listed(simulator, run_id, f"?target={VENT}") == ["open", "shut"]
    assert _listed(simulator, run_id, "?state=assigned") == ["open", "warm", "shut"]
    assert _listed(simulator, run_id, "?state=started&state=due") == []
    assert _listed(simulator, run_id, "?plan=other") == []


def test_a_revision_supersedes_what_it_leaves_out_and_each_revision_is_read(
    played: tuple[Simulator, Playback],
) -> None:
    simulator, found = played
    run_id = found.run_id
    _receipt(
        _call(
            simulator,
            "POST",
            f"/runs/{run_id}/plans",
            _plan(found, _level("open", 6 * HOUR), _level("shut", 8 * HOUR, 0.0)),
        )
    )

    revised = _receipt(
        _call(
            simulator,
            "POST",
            f"/runs/{run_id}/plans",
            _plan(found, _level("open", 6 * HOUR), revision=2),
        )
    )
    state = PlanState.model_validate(_call(simulator, "GET", f"/runs/{run_id}/plans/p").body)
    first = PlanState.model_validate(
        _call(simulator, "GET", f"/runs/{run_id}/plans/p?revision=1").body
    )

    assert revised.accepted
    assert state.plan.revision == 2 and len(first.plan.actions) == 2
    assert [(str(o.ref), o.status) for o in state.outcomes] == [("shut", OutcomeStatus.SUPERSEDED)]
    assert _listed(simulator, run_id) == ["open"]
    assert (
        _call(simulator, "GET", f"/runs/{run_id}/plans/p?revision=0").status
        == HTTPStatus.BAD_REQUEST
    )
    assert (
        _call(simulator, "GET", f"/runs/{run_id}/plans/p?revision=9").status == HTTPStatus.NOT_FOUND
    )
    assert _call(simulator, "GET", f"/runs/{run_id}/plans/q").status == HTTPStatus.NOT_FOUND


def test_chosen_actions_and_a_whole_plan_are_cancelled_as_the_local_operator(
    played: tuple[Simulator, Playback],
) -> None:
    simulator, found = played
    run_id = found.run_id
    epoch = found.state().epoch
    _receipt(
        _call(
            simulator,
            "POST",
            f"/runs/{run_id}/plans",
            _plan(
                found,
                _level("open", 6 * HOUR),
                _level("shut", 8 * HOUR, 0.0, after=["open"]),
                _level("again", 9 * HOUR),
            ),
        )
    )
    key = {"plan_id": "p", "epoch": epoch, "revision": 1, "ref": {"action_id": "open"}}
    stale = {**key, "revision": 9}

    cancelled = _receipt(
        _call(simulator, "POST", f"/runs/{run_id}/actions/cancel", json.dumps([key]).encode())
    )
    refused = _receipt(
        _call(simulator, "POST", f"/runs/{run_id}/actions/cancel", json.dumps([stale]).encode())
    )
    wrong = _receipt(
        _call(simulator, "POST", f"/runs/{run_id}/plans/p/cancel?revision=1&epoch={epoch + 1}")
    )
    whole = _receipt(
        _call(simulator, "POST", f"/runs/{run_id}/plans/p/cancel?revision=1&epoch={epoch}")
    )
    ends = {str(o.ref): o for o in found.plan("p").outcomes}

    assert cancelled.accepted and whole.accepted and not wrong.accepted
    # A stale key is said stale, and nothing is cancelled by it.
    assert (refused.cancelled, len(refused.stale)) == ((), 1)
    assert (ends["open"].status, ends["open"].cancelled_by) == (
        OutcomeStatus.CANCELLED,
        LOCAL_OPERATOR,
    )
    assert ends["shut"].status == OutcomeStatus.CANCELLED  # it waited for the one cancelled
    assert ends["again"].status == OutcomeStatus.CANCELLED  # with the whole plan
    assert _listed(simulator, run_id) == []
    missing = _call(simulator, "POST", f"/runs/{run_id}/plans/p/cancel?revision=1")
    assert missing.status == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    ("body", "said"),
    [
        (b"{not json", "not a plan"),
        (b'{"plan_id": "p"}', "not a plan"),
        (None, "not a plan"),  # an action's level NaN
        ("duplicate", "not a plan"),
    ],
)
def test_what_is_not_a_plan_is_refused_before_it_reaches_the_gateway(
    played: tuple[Simulator, Playback], body: bytes | str | None, said: str
) -> None:
    simulator, found = played
    if body is None:
        body = _plan(found, _level("open", 6 * HOUR)).replace(b'"level": 1.0', b'"level": NaN')
    elif body == "duplicate":
        body = _plan(found, _level("open", 6 * HOUR), _level("open", 7 * HOUR))
    assert isinstance(body, bytes)

    answered = _call(simulator, "POST", f"/runs/{found.run_id}/plans", body)

    assert answered.status == HTTPStatus.BAD_REQUEST
    assert isinstance(answered.body, dict) and said in str(answered.body["detail"])
    assert _call(simulator, "GET", f"/runs/{found.run_id}/plans/p").status == HTTPStatus.NOT_FOUND


def test_a_plan_for_another_epoch_or_for_someone_else_is_refused_whole(
    played: tuple[Simulator, Playback],
) -> None:
    simulator, found = played
    someone = {"kind": "person", "id": "someone"}

    stale = _receipt(
        _call(
            simulator,
            "POST",
            f"/runs/{found.run_id}/plans",
            _plan(found, _level("open", 6 * HOUR), epoch=5),
        )
    )
    theirs = _receipt(
        _call(
            simulator,
            "POST",
            f"/runs/{found.run_id}/plans",
            _plan(found, _level("open", 6 * HOUR, proposed_by=someone)),
        )
    )

    assert not stale.accepted and "stale" in " ".join(stale.errors)
    assert not theirs.accepted
    assert theirs.errors == ("local_operator may not propose open for someone",)
    assert _listed(simulator, found.run_id) == []


def test_a_target_the_local_operator_may_not_set_is_refused_at_once_with_its_reason() -> None:
    levels_only = AuthorisationConfig(
        version=2,
        groups=(
            AuthorisationGroup(
                group_id="local_operators",
                principals=frozenset({LOCAL_OPERATOR}),
                grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
            ),
        ),
    )
    with Simulator(authorisation=levels_only) as simulator:
        found = simulator.playbacks.made_once(
            SCENARIO, lambda _: Playback(simulator, SCENARIO, seconds_per_day=24.0, clock=_Clock())
        )
        receipt = _receipt(
            _call(
                simulator,
                "POST",
                f"/runs/{found.run_id}/plans",
                _plan(found, _target("warm", 7 * HOUR)),
            )
        )
        (refused,) = found.plan("p").outcomes

    assert receipt.accepted and [str(ref) for ref in receipt.refused] == ["warm"]
    assert (refused.status, refused.reason) == (
        OutcomeStatus.REFUSED,
        "local_operator is not authorised to set_target",
    )


@pytest.mark.parametrize(
    ("scenario_id", "plan", "refused"),
    [
        (SCENARIO, RunPlan.requested([(60.0, "no_fan", 0.5)]), "has no equipment 'no_fan'"),
        (SCENARIO, RunPlan.requested([(200 * DAY_S, VENT, 0.5)]), "within the run"),
        (SCENARIO, RunPlan.requested(targets=[(90.0, "heating_day", 20.0)]), "on the minute"),
        ("climate_box", RunPlan.requested(targets=[(60.0, "heating_day", 20.0)]), "heating loop"),
    ],
)
def test_an_action_given_is_checked_as_its_run_checks_its_plan(
    scenario_id: str, plan: RunPlan, refused: str
) -> None:
    config = scenario(PACKAGED, scenario_id)

    checked_actions(config, RunPlan.requested([(60.0, VENT, 0.5)]))
    with pytest.raises(InvalidRequest, match=refused):
        checked_actions(config, plan)


def test_a_recurrence_beyond_a_plans_occurrences_is_refused_whole(
    played: tuple[Simulator, Playback],
) -> None:
    simulator, found = played
    every_second = _level("tick", HOUR, every={"period": 1.0, "count": PLAN_OCCURRENCES + 1})

    receipt = _receipt(
        _call(simulator, "POST", f"/runs/{found.run_id}/plans", _plan(found, every_second))
    )

    assert not receipt.accepted and "occurrences" in " ".join(receipt.errors)


def test_the_routes_answer_what_they_cannot_do(played: tuple[Simulator, Playback]) -> None:
    simulator, found = played
    run_id = found.run_id

    assert actuation_respond(simulator, "GET", "/api/scenarios") is None
    assert _call(simulator, "GET", "/runs/nobody/actions").status == HTTPStatus.NOT_FOUND
    assert _call(simulator, "GET", f"/runs/{run_id}/plans").status == HTTPStatus.METHOD_NOT_ALLOWED
    assert (
        _call(simulator, "POST", f"/runs/{run_id}/actions").status == HTTPStatus.METHOD_NOT_ALLOWED
    )
    assert _call(simulator, "GET", f"/runs/{run_id}/elsewhere").status == HTTPStatus.NOT_FOUND
    bad = _call(simulator, "GET", f"/runs/{run_id}/actions?state=asleep")
    assert bad.status == HTTPStatus.BAD_REQUEST
    assert isinstance(bad.body, dict) and bad.body["problems"] == [
        {"field": "state", "message": "asleep"}
    ]
    found._gateway.finish()
    finished = _call(
        simulator, "POST", f"/runs/{run_id}/plans", _plan(found, _level("open", 6 * HOUR))
    )
    assert finished.status == HTTPStatus.CONFLICT


def test_the_targets_route_is_an_alias_of_a_revision_of_plan_targets(
    played: tuple[Simulator, Playback],
) -> None:
    """Given through the alias, then revised through the gateway's route,
    then through the alias again: each a revision of the one plan, the
    alias's own actions named afresh."""
    simulator, found = played
    alias = f"/api/scenarios/{SCENARIO}/playback/targets?targets=heating_night:18"

    assert respond(simulator, "POST", alias).status == HTTPStatus.OK
    held = found.plan(TARGETS_PLAN).plan
    revised = _receipt(
        _call(
            simulator,
            "POST",
            f"/runs/{found.run_id}/plans",
            json.dumps(
                held.model_dump(mode="json")
                | {
                    "revision": 2,
                    "actions": [
                        *held.model_dump(mode="json")["actions"],
                        _target("target_1", 9 * HOUR),
                    ],
                }
            ).encode(),
        )
    )
    again = respond(simulator, "POST", alias.replace("18", "19"))

    assert revised.accepted
    assert again.status == HTTPStatus.OK, again.body
    plan = found.plan(TARGETS_PLAN).plan
    assert plan.revision == 3
    assert [each.action_id for each in plan.actions] == ["target_0", "target_1", "target_2"]


def test_a_playback_started_held_waits_at_its_start(played: tuple[Simulator, Playback]) -> None:
    simulator, _ = played
    held = respond(simulator, "POST", "/api/scenarios/climate_box/playback/start?hold=true")
    wrong = respond(simulator, "POST", "/api/scenarios/climate_box/playback/start?hold=maybe")

    assert held.status == HTTPStatus.OK
    assert isinstance(held.body, dict) and held.body["playing"] is False
    assert wrong.status == HTTPStatus.BAD_REQUEST


def test_a_plan_is_given_over_http(played: tuple[Simulator, Playback]) -> None:
    simulator, found = played
    server = create_server(0, simulator=simulator)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    base = f"http://{host!s}:{port}/actuation/v1/runs/{found.run_id}"
    try:
        given = urllib.request.Request(
            f"{base}/plans", data=_plan(found, _level("open", 6 * HOUR)), method="POST"
        )
        with urllib.request.urlopen(given, timeout=30) as answer:
            receipt = Receipt.model_validate_json(answer.read())
        with urllib.request.urlopen(f"{base}/actions", timeout=30) as answer:
            listed = json.loads(answer.read())
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(
                urllib.request.Request(f"{base}/plans", data=b"{", method="POST"), timeout=30
            )
    finally:
        server.shutdown()
        server.server_close()

    assert receipt.accepted
    assert [each["ref"]["action_id"] for each in listed] == ["open"]
    assert refused.value.code == HTTPStatus.BAD_REQUEST
