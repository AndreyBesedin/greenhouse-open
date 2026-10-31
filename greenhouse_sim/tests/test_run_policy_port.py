"""A policy's port on a run played back (P15.3, decision 0061): the
protocol's contract held by its conformance check, through a harness that
steps a playback and delivers records into its logs as its producer does;
and what is the simulator's own: cursors kept apart from the consumer
interface's, the operator's plans unseen, a new epoch's logs started
again."""

import json
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Final
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from greenhouse_protocol.actions import SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.budget import (
    OBSERVATIONS_ONLY,
    ForecastProvider,
    ForecastUncertainty,
    InformationBasis,
    InformationBudget,
)
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.consumer import OutcomeBatch, check_polls
from greenhouse_protocol.contracts.gateway import STARTED_OVER, PlanState, Receipt
from greenhouse_protocol.contracts.policy import (
    POLICY,
    RIVAL,
    Delivered,
    PolicyPort,
    check_policy_port,
    conformance_policy_authorisation,
)
from greenhouse_protocol.contracts.policy_client import HttpPolicyPort, PortRefused
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.event import Event
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import ActionKey, At, Plan, PlannedAction, Principal

from greenhouse_sim.api import policy_server
from greenhouse_sim.api.policy_server import PolicyPortServer
from greenhouse_sim.services import playback
from greenhouse_sim.services.credentials import (
    Credentials,
    Role,
    credentials_file,
    new_credential,
    new_credential_for,
)
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.forecasts import (
    PERSISTED,
    PERSISTENCE,
    Forecaster,
    persistence_budget,
)
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.playback import (
    Playback,
    PlaybackCommand,
    PlaybackState,
    RecordsAfter,
    delivered,
)
from greenhouse_sim.services.policy_port import RunPolicyPort, policy_port
from greenhouse_sim.services.policy_requests import ServedPorts
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import DAY_S

# Its run's days cost next to nothing, and it has doors to set.
SCENARIO: Final = "airflow_box"
SECONDS_PER_DAY: Final = 24.0
HOUR: Final = timedelta(hours=1)


class _Delivered:
    """A forecaster of the forecasts a test delivers: each is issued once
    the clock reaches its issue, whatever the port has read of it."""

    def __init__(self, provider: ForecastProvider) -> None:
        self.provider = provider
        self._pending: list[Forecast] = []

    def deliver(self, forecasts: Sequence[Forecast]) -> None:
        self._pending += forecasts

    def issue_due(
        self,
        observed: Sequence[Observation],
        *,
        start: datetime,
        greenhouse_id: str,
        after: datetime | None,
        until: datetime,
    ) -> list[Forecast]:
        due = sorted((f for f in self._pending if f.issued_at <= until), key=lambda f: f.issued_at)
        self._pending = [f for f in self._pending if f.issued_at > until]
        return due


class _Delivering:
    """A playback, stepped by a test, whose logs also take the records the
    test delivers: each joins its log once the clock reaches its delivery,
    in delivery order, as its producer's do."""

    def __init__(self, played: Playback, budget: InformationBudget = OBSERVATIONS_ONLY) -> None:
        self.played = played
        self.budget = budget
        # The providers a test delivers forecasts for are a weather
        # service's, not made from the run.
        self.forecasters = tuple(_Delivered(provider) for provider in budget.forecasts)
        self._pending: list[Observation | Event] = []
        self._epoch = played.state().epoch
        self._observations: list[Observation] = []
        self._events: list[Event] = []
        self._read = {"observations": 0, "events": 0}
        # Once set, the run starts over just after its observations are next
        # read, and is stepped on to this moment of its new epoch.
        self.starts_over_to_s: float | None = None

    def deliver(self, records: Sequence[Delivered]) -> None:
        self._pending += [r for r in records if isinstance(r, Observation | Event)]
        for forecaster in self.forecasters:
            forecaster.deliver([r for r in records if isinstance(r, Forecast)])

    def advance(self, to: datetime) -> None:
        self.played.step_to((to - self.played.start).total_seconds())

    # What a port reads and gives.

    def state(self) -> PlaybackState:
        return self.played.state()

    def context(self, principal: Principal) -> CapabilityContext:
        return self.played.context(principal)

    def records_after(self, after: int, limit: int) -> RecordsAfter[Observation]:
        state = self._caught_up()
        chosen = tuple(self._observations[after : after + limit])
        more = after + len(chosen) < len(self._observations)
        if self.starts_over_to_s is not None:
            to_s, self.starts_over_to_s = self.starts_over_to_s, None
            # A restart plays on; held again, it is stepped.
            self.played.command(PlaybackCommand.RESTART)
            self.played.command(PlaybackCommand.PAUSE)
            self.advance(self.played.start + timedelta(seconds=to_s))
        return RecordsAfter(records=chosen, next=after + len(chosen), has_more=more, state=state)

    def events_after(self, after: int, limit: int) -> RecordsAfter[Event]:
        state = self._caught_up()
        chosen = tuple(self._events[after : after + limit])
        more = after + len(chosen) < len(self._events)
        return RecordsAfter(records=chosen, next=after + len(chosen), has_more=more, state=state)

    def outcomes_after(self, after: int, limit: int) -> tuple[OutcomeBatch, PlaybackState]:
        return self.played.outcomes_after(after, limit)

    def plan(self, plan_id: str, revision: int | None = None) -> PlanState:
        return self.played.plan(plan_id, revision)

    def submit(self, plan: Plan, *, by: Principal) -> Receipt:
        return self.played.submit(plan, by=by)

    def cancel(self, keys: Sequence[ActionKey], *, by: Principal) -> Receipt:
        return self.played.cancel(keys, by=by)

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int, by: Principal) -> Receipt:
        return self.played.cancel_plan(plan_id, revision=revision, epoch=epoch, by=by)

    def owner_of(self, outcome: ActionOutcome) -> Principal | None:
        return self.played.owner_of(outcome)

    def _caught_up(self) -> PlaybackState:
        state = self.played.state()
        if state.epoch != self._epoch:
            # The run started over: its logs start again, as a producer's do.
            self._epoch, self._observations, self._events = state.epoch, [], []
            self._read = {"observations": 0, "events": 0}
        now = state.simulated_now
        due = [r for r in self._pending if delivered(r) <= now]
        self._pending = [r for r in self._pending if delivered(r) > now]
        observations = self._drained(self.played.records_after, "observations")
        events = self._drained(self.played.events_after, "events")
        self._observations += sorted(
            [*observations, *(r for r in due if isinstance(r, Observation))], key=delivered
        )
        self._events += sorted([*events, *(r for r in due if isinstance(r, Event))], key=delivered)
        return state

    def _drained[R: (Observation, Event)](
        self, read: Callable[[int, int], RecordsAfter[R]], log: str
    ) -> list[R]:
        records: list[R] = []
        while True:
            cut = read(self._read[log], 10**6)
            records += cut.records
            self._read[log] = cut.next
            if not cut.has_more:
                return records


class _Harness(RunPolicyPort):
    """A port on a run a test steps and delivers records to."""

    def __init__(self, run: _Delivering, principal: Principal) -> None:
        super().__init__(run, principal, budget=run.budget, forecasters=run.forecasters)
        self._delivering = run

    def advance(self, to: datetime) -> None:
        self._delivering.advance(to)

    def deliver(self, records: Sequence[Delivered]) -> None:
        self._delivering.deliver(records)

    def open(self, principal: Principal) -> PolicyPort:
        return RunPolicyPort(
            self._delivering,
            principal,
            budget=self._delivering.budget,
            forecasters=self._delivering.forecasters,
        )


def _port(
    simulator: Simulator,
    scenario_id: str = SCENARIO,
    authorisation: AuthorisationConfig | None = None,
    budget: InformationBudget = OBSERVATIONS_ONLY,
) -> tuple[_Harness, Playback]:
    """A port for `POLICY` on a new playback of a scenario's run, played by
    a test, under the conformance check's authorisation or `authorisation`,
    and `budget`."""
    played = Playback(simulator, scenario_id)
    played.authorise(authorisation or conformance_policy_authorisation())
    return _Harness(_Delivering(played, budget), POLICY), played


@pytest.mark.parametrize(
    "scenario_id", [SCENARIO, pytest.param("climate_box", marks=pytest.mark.slow)]
)
def test_a_port_on_a_run_keeps_the_contract(simulator: Simulator, scenario_id: str) -> None:
    def make(authorisation: AuthorisationConfig, start: datetime) -> _Harness:
        return _port(simulator, scenario_id, authorisation)[0]

    assert check_policy_port(make, Playback(simulator, scenario_id).start) == []


# What a weather service forecasts, to a run that is not made of it.
WEATHER_SERVICE: Final = InformationBudget(
    budget_id="weather_service",
    forecasts=(
        ForecastProvider(
            provider_id="weather_service",
            version="2",
            basis=InformationBasis.EXTERNAL,
            quantities=frozenset({ObservationType.OUTSIDE_AIR_TEMPERATURE_C}),
            issued_every_s=HOUR.total_seconds(),
            horizon_s=DAY_S,
            uncertainty=ForecastUncertainty.NONE,
        ),
    ),
)


def test_a_port_with_forecasts_keeps_the_contract(simulator: Simulator) -> None:
    def make(authorisation: AuthorisationConfig, start: datetime) -> _Harness:
        return _port(simulator, authorisation=authorisation, budget=WEATHER_SERVICE)[0]

    assert check_policy_port(make, Playback(simulator, SCENARIO).start) == []


def _forecast(issued_at: datetime, name: str = "f") -> Forecast:
    return Forecast(
        forecast_id=name,
        greenhouse_id="airflow_box",
        provider_id="weather_service",
        provider_version="2",
        issued_at=issued_at,
        valid_from=issued_at + HOUR,
        valid_until=issued_at + 2 * HOUR,
        quantity=ObservationType.OUTSIDE_AIR_TEMPERATURE_C,
        value=12.5,
    )


def test_a_forecast_reaches_the_port_no_earlier_than_it_was_issued(simulator: Simulator) -> None:
    port, played = _port(simulator, budget=WEATHER_SERVICE)
    port.deliver([_forecast(played.start + 2 * HOUR)])

    port.advance(played.start + HOUR)
    early = port.forecasts()
    port.advance(played.start + 2 * HOUR)
    on_time = port.forecasts(after=early.next)

    assert early.forecasts == ()
    assert [f.forecast_id for f in on_time.forecasts] == ["f"]
    assert on_time.simulated_now == played.start + 2 * HOUR
    assert port.forecasts(after=7).forecasts == ()


def test_a_new_epoch_starts_the_forecasts_again(simulator: Simulator) -> None:
    port, played = _port(simulator, budget=WEATHER_SERVICE)
    port.deliver([_forecast(played.start + HOUR)])
    port.advance(played.start + HOUR)
    before = port.forecasts()
    assert [f.forecast_id for f in before.forecasts] == ["f"]

    played.command(PlaybackCommand.RESTART)
    played.command(PlaybackCommand.PAUSE)
    port.advance(played.start + HOUR)
    after = port.forecasts(after=before.next)

    assert (after.epoch, after.forecasts) == (before.epoch + 1, ())
    assert check_polls([before, after], greenhouse_id=port.run().greenhouse_id) == []


def test_the_same_forecasts_are_read_by_either_transport(simulator: Simulator) -> None:
    near, played = _port(simulator, budget=WEATHER_SERVICE)
    far_port, _ = _port(simulator, budget=WEATHER_SERVICE)
    with _served(far_port._delivering, [POLICY]) as (url, tokens):
        far = HttpPolicyPort(url, tokens[POLICY])
        for port in (near, far_port):
            port.deliver([_forecast(played.start + HOUR)])
            port.advance(played.start + HOUR)
        batches = [port.forecasts().model_dump(exclude={"run_id"}) for port in (near, far)]
        assert far.budget() == near.budget() == WEATHER_SERVICE

    assert batches[0] == batches[1]
    assert batches[0]["forecasts"] != ()


def test_a_budget_the_port_cannot_serve_is_refused_when_it_is_opened(
    simulator: Simulator,
) -> None:
    played = Playback(simulator, SCENARIO)
    (served,) = WEATHER_SERVICE.forecasts

    def refused(budget: InformationBudget, *forecasters: Forecaster) -> str:
        with pytest.raises(InvalidRequest) as error:
            RunPolicyPort(played, POLICY, budget=budget, forecasters=forecasters)
        return error.value.message

    def named(**changes: object) -> InformationBudget:
        provider = served.model_copy(update=changes)
        return InformationBudget(budget_id="other", forecasts=(provider,))

    nobody = refused(WEATHER_SERVICE)
    assert "no forecaster serves" in nobody
    service = _Delivered(served)
    assert "no forecaster serves" in refused(named(version="3"), service)
    assert "not served as the budget names it" in refused(
        named(horizon_s=served.horizon_s * 2), service
    )
    assert "not served as the budget names it" in refused(
        named(quantities=frozenset({ObservationType.OUTSIDE_WIND_SPEED_M_S})), service
    )
    assert "full state" in refused(InformationBudget(budget_id="all", full_state=True, oracle=True))
    # Made from observations the run does not make: the airflow box has no
    # weather station.
    assert "observes no" in refused(persistence_budget(PERSISTED), PERSISTENCE)
    # Named as it is served, it is opened.
    assert RunPolicyPort(played, POLICY, budget=WEATHER_SERVICE, forecasters=(service,))


def test_a_budget_that_gives_the_truth_is_labelled_an_oracle() -> None:
    (served,) = WEATHER_SERVICE.forecasts
    oracle = served.model_copy(update={"basis": InformationBasis.PRIVILEGED})

    with pytest.raises(ValueError, match="labelled an oracle"):
        InformationBudget(budget_id="future", forecasts=(oracle,))
    with pytest.raises(ValueError, match="labelled an oracle"):
        InformationBudget(budget_id="future", forecasts=(served,), oracle=True)
    assert InformationBudget(budget_id="future", forecasts=(oracle,), oracle=True).oracle
    assert not WEATHER_SERVICE.oracle


def test_a_cursor_the_port_never_gave_is_answered_with_nothing(simulator: Simulator) -> None:
    port, played = _port(simulator)
    # Past the walk at noon, the airflow box's only observations.
    port.advance(played.start + 13 * HOUR)

    unknown = port.observations(after=3)
    first = port.observations()

    assert (unknown.after, unknown.next, unknown.observations) == (3, 3, ())
    assert first.observations != ()
    assert port.observations(after=first.next).after == first.next


def test_the_operators_plans_and_their_outcomes_are_not_a_policys(simulator: Simulator) -> None:
    port, played = _port(simulator)
    door = min(device.device_id for device in port.context().devices)
    opened = PlannedAction(
        action_id="open",
        action=SetLevel(device_id=door, level=1.0),
        timing=At(at=played.start + HOUR),
        proposed_by=LOCAL_OPERATOR,
    )
    run = port.run()
    receipt = played.submit(
        Plan(
            plan_id="operators", run_id=run.run_id, epoch=run.epoch, revision=1, actions=(opened,)
        ),
        by=LOCAL_OPERATOR,
    )
    assert receipt.accepted, receipt.errors
    port.advance(played.start + 2 * HOUR)

    assert port.plan("operators") is None
    assert port.outcomes().outcomes == ()
    (operators,) = played.outcomes_after(0, 10)[0].outcomes
    assert operators.plan_id == "operators"


def test_a_new_epoch_starts_the_ports_logs_again(simulator: Simulator) -> None:
    port, played = _port(simulator)
    port.advance(played.start + 13 * HOUR)
    before = port.observations()
    assert before.observations != ()

    # A restart plays on; the test holds it again, to step it.
    played.command(PlaybackCommand.RESTART)
    played.command(PlaybackCommand.PAUSE)
    port.advance(played.start + 13 * HOUR)
    after = port.observations(after=before.next)
    again = port.observations()

    assert (after.epoch, after.observations) == (before.epoch + 1, ())
    assert again.epoch == before.epoch + 1
    assert [o.observation_id for o in again.observations] == [
        o.observation_id for o in before.observations
    ]
    assert check_polls([before, after, again], greenhouse_id=port.run().greenhouse_id) == []


def test_after_a_restart_a_port_gives_its_own_actions_cancelled_and_no_one_elses(
    simulator: Simulator,
) -> None:
    port, played = _port(simulator)
    rival = port.open(RIVAL)
    door = min(device.device_id for device in port.context().devices)
    run = port.run()
    for opened, principal in ((port, POLICY), (rival, RIVAL)):
        later = PlannedAction(
            action_id="open",
            action=SetLevel(device_id=door, level=1.0),
            timing=At(at=played.start + 5 * HOUR),
            proposed_by=principal,
        )
        plan = Plan(
            plan_id=principal.id, run_id=run.run_id, epoch=run.epoch, revision=1, actions=(later,)
        )
        assert opened.submit(plan).accepted
    port.advance(played.start + HOUR)

    played.command(PlaybackCommand.RESTART)

    (mine,) = port.outcomes().outcomes
    assert (mine.plan_id, mine.status, mine.epoch) == (POLICY.id, OutcomeStatus.CANCELLED, 1)
    assert STARTED_OVER in (mine.reason or "")
    assert [o.plan_id for o in rival.outcomes().outcomes] == [RIVAL.id]


def test_a_run_that_starts_over_while_a_port_reads_it_is_read_in_its_new_epoch(
    simulator: Simulator,
) -> None:
    """The run starts over between the port's first read of the run's log
    and its read again from the start: what the port keeps, and the cursors
    it gives, are of the epoch it read last."""
    port, played = _port(simulator)
    port.advance(played.start + 13 * HOUR)
    port._delivering.starts_over_to_s = 13 * HOUR.total_seconds()

    first = port.observations()
    port.advance(played.start + 37 * HOUR)
    then = port.observations(after=first.next)

    assert (first.epoch, then.epoch) == (1, 1)
    assert first.observations != () and then.observations != ()
    assert check_polls([first, then], greenhouse_id=port.run().greenhouse_id) == []


def test_a_port_is_opened_on_a_run_played_back(
    simulator: Simulator, no_playbacks: Callable[[], None]
) -> None:
    playback.start(simulator, SCENARIO, SECONDS_PER_DAY, hold=True)
    run_id = playback.playback(simulator, SCENARIO).run_id

    port = policy_port(simulator.playbacks, run_id, POLICY)

    assert port.run().run_id == run_id
    assert port.context().principal == POLICY
    with pytest.raises(NotFound):
        policy_port(simulator.playbacks, "no-such-run", POLICY)


# Over the network (P15.5).


@contextmanager
def _served(
    run: _Delivering, principals: Sequence[Principal], *, role: Role = Role.POLICY
) -> Iterator[tuple[str, dict[Principal, str]]]:
    """A port's server on `run`, its credentials one token for each of
    `principals`, in `role`: its root URL, and each principal's token."""
    tokens: dict[Principal, str] = {}
    credentials = []
    for principal in principals:
        tokens[principal], credential = new_credential(principal, role)
        credentials.append(credential)
    server = PolicyPortServer(
        ServedPorts(
            run,
            Credentials(credentials=tuple(credentials)),
            budget=run.budget,
            forecasters=run.forecasters,
        )
    )
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host!s}:{port}", tokens
    finally:
        server.shutdown()
        server.server_close()


class _OverHttp(HttpPolicyPort):
    """A port over HTTP on a run a test steps and delivers records to."""

    def __init__(self, url: str, tokens: dict[Principal, str], run: _Delivering) -> None:
        super().__init__(url, tokens[POLICY])
        self._url, self._tokens, self._run = url, tokens, run

    def advance(self, to: datetime) -> None:
        self._run.advance(to)

    def deliver(self, records: Sequence[Delivered]) -> None:
        self._run.deliver(records)

    def open(self, principal: Principal) -> PolicyPort:
        return HttpPolicyPort(self._url, self._tokens[principal])


@pytest.mark.parametrize("budget", [OBSERVATIONS_ONLY, WEATHER_SERVICE])
def test_a_port_over_the_network_keeps_the_contract(
    simulator: Simulator, budget: InformationBudget
) -> None:
    with ExitStack() as servers:

        def make(authorisation: AuthorisationConfig, start: datetime) -> _OverHttp:
            harness, _ = _port(simulator, SCENARIO, authorisation, budget)
            run = harness._delivering
            url, tokens = servers.enter_context(_served(run, [POLICY, RIVAL]))
            return _OverHttp(url, tokens, run)

        assert check_policy_port(make, Playback(simulator, SCENARIO).start) == []


def test_the_same_plan_has_the_same_receipt_by_either_transport(simulator: Simulator) -> None:
    near, near_run = _port(simulator)
    far_port, far_run = _port(simulator)
    with _served(far_port._delivering, [POLICY]) as (url, tokens):
        far = HttpPolicyPort(url, tokens[POLICY])
        door = min(device.device_id for device in near.context().devices)
        receipts = []
        for port in (near, far):
            run = port.run()
            plans = [
                Plan(
                    plan_id=plan_id,
                    run_id=run.run_id,
                    epoch=run.epoch,
                    revision=1,
                    actions=(
                        PlannedAction(
                            action_id="open",
                            action=SetLevel(device_id=door, level=1.0),
                            timing=At(at=near_run.start + HOUR),
                            proposed_by=proposer,
                        ),
                    ),
                )
                for plan_id, proposer in (("mine", POLICY), ("for_the_operator", LOCAL_OPERATOR))
            ]
            receipts.append([port.submit(plan) for plan in plans])

        assert receipts[0] == receipts[1]
        assert [receipt.accepted for receipt in receipts[1]] == [True, False]
        assert far.plan("mine") == near.plan("mine") is not None
        assert far.plan("for_the_operator") is None
        assert far_run.run_id == near_run.run_id


def _status(url: str, path: str, token: str | None = None, method: str = "GET") -> int:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    data = b"{}" if method == "POST" else None
    try:
        with urlopen(Request(url + path, data=data, method=method, headers=headers)) as answer:
            status: int = answer.status
            return status
    except HTTPError as refused:
        return refused.code


def test_the_port_answers_policies_alone_and_none_of_the_local_apis_routes(
    simulator: Simulator,
) -> None:
    port, _ = _port(simulator)
    with (
        _served(port._delivering, [POLICY]) as (url, tokens),
        _served(port._delivering, [LOCAL_OPERATOR], role=Role.OPERATOR) as (operators, held),
    ):
        token = tokens[POLICY]

        assert _status(url, "/policy/v1/run", token) == HTTPStatus.OK
        assert _status(url, "/policy/v1/run") == HTTPStatus.UNAUTHORIZED
        assert _status(url, "/policy/v1/run", "not-a-token") == HTTPStatus.UNAUTHORIZED
        assert _status(operators, "/policy/v1/run", held[LOCAL_OPERATOR]) == HTTPStatus.FORBIDDEN
        for route in (
            "/api/scenarios",
            "/consumer/v1/runs",
            f"/actuation/v1/runs/{port.run().run_id}/plans/x",
            "/policy/v2/run",
        ):
            assert _status(url, route, token) == HTTPStatus.NOT_FOUND, route
        assert _status(url, "/policy/v1/plans", token) == HTTPStatus.METHOD_NOT_ALLOWED
        assert _status(url, "/policy/v1/run", token, "PUT") == HTTPStatus.METHOD_NOT_ALLOWED
        assert _status(url, "/policy/v1/plans", token, "POST") == HTTPStatus.BAD_REQUEST
        with pytest.raises(PortRefused) as refused:
            HttpPolicyPort(url, "not-a-token").context()
        assert refused.value.status == HTTPStatus.UNAUTHORIZED
        assert refused.value.detail == "no credential holds that token"


def test_a_credentials_file_keeps_each_tokens_hash_and_never_the_token(tmp_path: Path) -> None:
    token, credential = new_credential(POLICY)
    rival_token, rival = new_credential(RIVAL)
    path = tmp_path / "credentials.json"
    path.write_text(Credentials(credentials=(credential, rival)).model_dump_json())

    read = credentials_file(path)

    assert token not in path.read_text() and rival_token not in path.read_text()
    assert read.holder(token) == credential
    assert read.holder(rival_token) == rival
    assert read.holder(token + "x") is None
    twice = Credentials(credentials=(credential,)).model_dump(mode="json")
    twice["credentials"] *= 2
    path.write_text(json.dumps(twice))
    with pytest.raises(InvalidRequest, match="more than one credential"):
        credentials_file(path)
    with pytest.raises(InvalidRequest, match="kind:id"):
        new_credential_for("naive_heating")


def test_the_command_makes_a_credential_and_names_what_it_serves(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert policy_server.main(["--new-credential", "policy:naive_heating"]) == 0
    printed = capsys.readouterr().out.splitlines()
    token = printed[0].removeprefix("token, for its holder alone: ")
    credential = Credentials.model_validate(
        {"credentials": [json.loads(printed[1].removeprefix("its credential, for the file: "))]}
    )
    assert credential.holder(token) is not None
    with pytest.raises(SystemExit):
        policy_server.main([])
