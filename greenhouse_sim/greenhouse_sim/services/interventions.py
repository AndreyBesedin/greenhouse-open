"""What a change given to an epoch is, as its log writes it (P17.8, decision
0065): a target changed, a plan given, actions or a plan cancelled, in the
gateway's own words, so that applying an entry again is the gateway being
given the same thing.

`Logged` is what a log entry's `what` holds. `Asked` is what someone other than
the epoch's worker asks of it through the store: the same, but for a target
change, whose moment is the worker's to choose, the next minute of the epoch's
clock when it takes the request.

A person's change reaches an epoch by a request written to the store (`ask`),
and the epoch's worker takes it between its moments, logs it and acts on it: the
store is the only channel between a worker and the API, and the worker the only
writer of its log. So a change asked for is not yet a change given, and `changes`
says which it has become.
"""

from typing import TYPE_CHECKING, Annotated, Final, Literal

from greenhouse_protocol.actions import SetTarget
from greenhouse_protocol.plan import ActionKey, Plan, Principal, PrincipalKind
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, read_as
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.run_store import Answer, EpochStore, LogEntry, ObjectStore, Status
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.runs import Commanded

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator


class _Change(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class TargetsChanged(_Change):
    """Targets changed: each its moment in seconds, its target and its value
    in °C, as a run's `&targets=` writes them."""

    kind: Literal["targets_changed"] = "targets_changed"
    changes: tuple[Commanded, ...]


class TargetsAsked(_Change):
    """Targets to change, by name, in °C, from the epoch's next minute."""

    kind: Literal["targets"] = "targets"
    targets: dict[str, float]


class PlanGiven(_Change):
    """A plan, or a revision of one, given to the epoch's gateway."""

    kind: Literal["plan"] = "plan"
    plan: Plan


class ActionsCancelled(_Change):
    """Chosen actions cancelled, by the keys they stood under when seen."""

    kind: Literal["cancel"] = "cancel"
    keys: tuple[ActionKey, ...]


class PlanCancelled(_Change):
    """A whole plan cancelled, as its revision in its epoch stood."""

    kind: Literal["cancel_plan"] = "cancel_plan"
    plan_id: str
    revision: int
    epoch: int


Logged = Annotated[
    TargetsChanged | PlanGiven | ActionsCancelled | PlanCancelled, Field(discriminator="kind")
]
Asked = Annotated[
    TargetsAsked | PlanGiven | ActionsCancelled | PlanCancelled, Field(discriminator="kind")
]

LOGGED: Final = TypeAdapter[Logged](Logged)
ASKED: Final = TypeAdapter[Asked](Asked)

_BY_MARK: Final = ":"


def spelled(principal: Principal) -> str:
    """Who gave a change, as a log entry says it."""
    return f"{principal.kind.value}{_BY_MARK}{principal.id}"


def principal_of(by: str) -> Principal:
    """Who gave a change a log entry names."""
    kind, _, identifier = by.partition(_BY_MARK)
    return Principal(kind=PrincipalKind(kind), id=identifier)


class ChangeAsked(BaseModel):
    """A change asked of an epoch: the name its worker will know it by."""

    model_config = ConfigDict(frozen=True)

    request: str


class EpochChanges(BaseModel):
    """What has become of the changes asked of an epoch: those logged, in
    order, those refused, and those no worker has taken yet. An epoch that has
    ended takes no more: whatever is still waiting then is never taken."""

    model_config = ConfigDict(frozen=True)

    status: Status
    log: list[LogEntry]
    refused: list[Answer]
    waiting: list[str]


def _epoch(simulator: Simulator, run_id: str, epoch: int) -> EpochStore:
    objects: ObjectStore | None = simulator.runs
    if objects is None:
        raise NotFound("this simulator keeps no runs: it was made with no run store")
    if epoch not in stored_epochs(objects, run_id):
        raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
    return EpochStore(objects, run_id, epoch)


def ask(simulator: Simulator, run_id: str, epoch: int, body: bytes) -> ChangeAsked:
    """Asks an epoch for a change the body writes (`Asked`), as the local
    operator, who is whoever reaches the local API (decision 0052). Its worker
    has its own simulator, so what the server's authorisation forbids is
    refused here. An epoch no one is to work takes no change: a moment past is
    changed by a fork, and an interrupted epoch once it is resumed."""
    asked = read_as("a change", lambda: ASKED.validate_json(body))
    kept = _epoch(simulator, run_id, epoch)
    status = kept.manifest().status
    if status not in (Status.QUEUED, Status.RUNNING):
        raise Conflict(
            f"epoch {epoch} of {run_id} is {status}: it takes no more changes; a fork acts "
            "from a moment of it"
        )
    _check_allowed(simulator, asked)
    return ChangeAsked(request=kept.ask(ASKED.dump_python(asked, mode="json")))


def _check_allowed(simulator: Simulator, asked: Asked) -> None:
    allowed = simulator.authorisation.allows
    match asked:
        case TargetsAsked(targets=targets):
            for name, value in targets.items():
                if not allowed(LOCAL_OPERATOR, _set_target(name, value)):
                    raise InvalidRequest(f"{LOCAL_OPERATOR.id} may not change {name}")
        case PlanGiven(plan=plan):
            for planned in plan.actions:
                if not allowed(LOCAL_OPERATOR, planned.action):
                    raise InvalidRequest(
                        f"{LOCAL_OPERATOR.id} may not {planned.action.kind} ({planned.action_id})"
                    )
        case _:
            pass


def _set_target(name: str, value: float) -> SetTarget:
    return read_as("a target", lambda: SetTarget.model_validate({"target": name, "value_c": value}))


def changes(simulator: Simulator, run_id: str, epoch: int) -> EpochChanges:
    """What has become of the changes asked of an epoch."""
    kept = _epoch(simulator, run_id, epoch)
    log = kept.logged()
    refused = kept.answers()
    logged = {entry.request for entry in log}
    answered = {answer.request for answer in refused}
    return EpochChanges(
        status=kept.manifest().status,
        log=log,
        refused=refused,
        waiting=[each for each in kept.requests() if each not in logged | answered],
    )
