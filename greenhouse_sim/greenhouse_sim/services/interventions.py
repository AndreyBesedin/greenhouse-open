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

The epoch keeps its authorisation (decision 0072): the rights it begins under,
unless they are the local operator's, are its log's first entry, and each change
of them made while it runs is an entry at its moment (`AuthorisationChanged`). A
log with no such first entry began under the local operator's rights, so that an
epoch begun under them, as every one kept before was, has the log and the digest
it had. A change of the simulator's authorisation reaches an epoch no playback of
it plays as a request in the store, as any change does (`authorise_kept`), which
only the simulator asks: the API takes none.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Final, Literal

from greenhouse_protocol.actions import SetLevel, SetTarget
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.plan import ActionKey, At, Plan, PlannedAction, Principal, PrincipalKind
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, read_as
from greenhouse_sim.services.gateway import LOCAL_AUTHORISATION, LOCAL_OPERATOR
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


class LevelsAsked(_Change):
    """Devices to set, by name, doors and vents included, from the moment it
    is given: a plan of them, as the epoch's gateway takes one."""

    kind: Literal["levels"] = "levels"
    levels: dict[str, float]


class AuthorisationChanged(_Change):
    """Who may do what on the epoch from the moment it is given, whole: the
    simulator's authorisation (decision 0052), which its gateway enforces from
    then on. Given by the simulator, never asked through the API."""

    kind: Literal["authorisation"] = "authorisation"
    authorisation: AuthorisationConfig


Logged = Annotated[
    TargetsChanged | PlanGiven | ActionsCancelled | PlanCancelled | AuthorisationChanged,
    Field(discriminator="kind"),
]
Asked = Annotated[
    TargetsAsked | LevelsAsked | PlanGiven | ActionsCancelled | PlanCancelled,
    Field(discriminator="kind"),
]
# What a request in the store may hold: a change asked, or one of the
# simulator's authorisation, which it alone writes.
Requested = Annotated[
    TargetsAsked
    | LevelsAsked
    | PlanGiven
    | ActionsCancelled
    | PlanCancelled
    | AuthorisationChanged,
    Field(discriminator="kind"),
]

LOGGED: Final = TypeAdapter[Logged](Logged)
ASKED: Final = TypeAdapter[Asked](Asked)
REQUESTED: Final = TypeAdapter[Requested](Requested)
# The statuses of an epoch a worker works, or will: those a change is asked of.
_WORKED: Final = (Status.QUEUED, Status.RUNNING)

_BY_MARK: Final = ":"


def levels_plan(
    levels: Mapping[str, float],
    *,
    run_id: str,
    epoch: int,
    start: datetime,
    at_s: float,
    plan_id: str,
) -> Plan:
    """Devices set at a moment, as a plan of its own for a run's gateway."""
    if not levels:
        raise InvalidRequest("levels wants device:level pairs, and none was given")
    return read_as(
        "levels",
        lambda: Plan(
            plan_id=plan_id,
            run_id=run_id,
            epoch=epoch,
            revision=1,
            actions=tuple(
                PlannedAction(
                    action_id=f"set_{index}",
                    action=SetLevel(device_id=device, level=level),
                    timing=At(at=start + timedelta(seconds=at_s)),
                    proposed_by=LOCAL_OPERATOR,
                )
                for index, (device, level) in enumerate(levels.items())
            ),
        ),
    )


def started_under(authorisation: AuthorisationConfig) -> AuthorisationChanged | None:
    """The entry that begins the log of an epoch begun under `authorisation`:
    none for the local operator's, which a log with none means."""
    if authorisation == LOCAL_AUTHORISATION:
        return None
    return AuthorisationChanged(authorisation=authorisation)


def begun_under(log: Sequence[LogEntry]) -> tuple[AuthorisationConfig, int]:
    """The authorisation an epoch's log says it began under, and how many of
    its entries say so: its first, if that is an authorisation given at the run's
    start, and else none, the local operator's."""
    if log and log[0].given_s == 0:
        match LOGGED.validate_python(log[0].what):
            case AuthorisationChanged(authorisation=authorisation):
                return authorisation, 1
            case _:
                pass
    return LOCAL_AUTHORISATION, 0


def in_force_after(log: Sequence[LogEntry]) -> AuthorisationConfig:
    """The authorisation in force once the entries of `log` are given: the
    last change of it among them, or, with none, the local operator's."""
    for entry in reversed(log):
        match LOGGED.validate_python(entry.what):
            case AuthorisationChanged(authorisation=authorisation):
                return authorisation
            case _:
                pass
    return LOCAL_AUTHORISATION


def log_start(epoch: EpochStore, authorisation: AuthorisationConfig) -> None:
    """Begins the log of an epoch not yet started with the authorisation it
    begins under, if it needs saying (`started_under`)."""
    began = started_under(authorisation)
    if began is not None:
        epoch.append_log(
            LogEntry(
                seq=0,
                at_s=0.0,
                given_s=0.0,
                by=spelled(LOCAL_OPERATOR),
                what=began.model_dump(mode="json"),
            )
        )


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
    order, those refused, those no worker has taken yet, and those its worker
    is done with. A worker logs a change before it acts on it, and may refuse
    it then: a request logged is acted on once it is done and not refused. An
    epoch that has ended takes no more: whatever is still waiting then is never
    taken."""

    model_config = ConfigDict(frozen=True)

    status: Status
    log: list[LogEntry]
    refused: list[Answer]
    waiting: list[str]
    done: list[str]


def _epoch(simulator: Simulator, run_id: str, epoch: int) -> EpochStore:
    objects: ObjectStore | None = simulator.runs
    if objects is None:
        raise NotFound("this simulator keeps no runs: it was made with no run store")
    if epoch not in stored_epochs(objects, run_id):
        raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
    return EpochStore(objects, run_id, epoch)


def ask(simulator: Simulator, run_id: str, epoch: int, body: bytes) -> ChangeAsked:
    """Asks an epoch for a change the body writes (`Asked`), as the local
    operator, who is whoever reaches the local API (decision 0052). What the
    server's authorisation forbids is refused here, saying so, before a worker
    refuses it under the epoch's. An epoch no one is to work takes no change: a
    moment past is changed by a fork, and an interrupted epoch once it is resumed."""
    asked = read_as("a change", lambda: ASKED.validate_json(body))
    kept = _epoch(simulator, run_id, epoch)
    status = kept.manifest().status
    if status not in _WORKED:
        raise Conflict(
            f"epoch {epoch} of {run_id} is {status}: it takes no more changes; a fork acts "
            "from a moment of it"
        )
    check_allowed(simulator, asked)
    return ChangeAsked(request=kept.ask(ASKED.dump_python(asked, mode="json")))


def check_allowed(simulator: Simulator, asked: Asked) -> None:
    """Refuses what the server's authorisation forbids the local operator, as
    it is asked: the epoch's worker decides it again under the epoch's own."""
    allowed = simulator.authorisation.allows
    match asked:
        case TargetsAsked(targets=targets):
            for name, value in targets.items():
                if not allowed(LOCAL_OPERATOR, _set_target(name, value)):
                    raise InvalidRequest(f"{LOCAL_OPERATOR.id} may not change {name}")
        case LevelsAsked(levels=levels):
            for device, level in levels.items():
                if not allowed(LOCAL_OPERATOR, _set_level(device, level)):
                    raise InvalidRequest(f"{LOCAL_OPERATOR.id} may not set {device}")
        case PlanGiven(plan=plan):
            for planned in plan.actions:
                if not allowed(LOCAL_OPERATOR, planned.action):
                    raise InvalidRequest(
                        f"{LOCAL_OPERATOR.id} may not {planned.action.kind} ({planned.action_id})"
                    )
        case _:
            pass


def _set_level(device: str, level: float) -> SetLevel:
    return read_as(
        "a level", lambda: SetLevel.model_validate({"device_id": device, "level": level})
    )


def _set_target(name: str, value: float) -> SetTarget:
    return read_as("a target", lambda: SetTarget.model_validate({"target": name, "value_c": value}))


def changes(simulator: Simulator, run_id: str, epoch: int) -> EpochChanges:
    """What has become of the changes asked of an epoch."""
    kept = _epoch(simulator, run_id, epoch)
    # Read in the order opposite to the one the worker writes in (log, answer,
    # done; an epoch's status as it ends, after all it took): a request read as
    # done then has its entry and any answer already there to be read, and an
    # epoch read as ended has every answer it gave. Read the other way, an
    # answer written between the reads of the answers and of those done would
    # leave a refused change read as taken.
    done = kept.done_requests()
    status = kept.manifest().status
    log = kept.logged()
    refused = kept.answers()
    logged = {entry.request for entry in log}
    answered = {answer.request for answer in refused}
    return EpochChanges(
        status=status,
        log=log,
        refused=refused,
        waiting=[each for each in kept.requests() if each not in logged | answered],
        done=done,
    )


def authorise_kept(simulator: Simulator, authorisation: AuthorisationConfig) -> None:
    """Asks every epoch of the simulator's store that a worker works, will work
    or may carry on, and that no playback of it plays, to take `authorisation`
    from its next moment: a request, taken in the order of the requests, and
    logged where it is taken. Those its playbacks play are told by them, at
    their clocks' moments. Under the simulator's lock of its authorisation, so
    that the changes are asked in the order they were made."""
    objects: ObjectStore | None = simulator.runs
    if objects is None:
        return
    played = simulator.playbacks.kept()
    asked = AuthorisationChanged(authorisation=authorisation).model_dump(mode="json")
    for run_id in objects.children():
        for number in stored_epochs(objects, run_id):
            if (run_id, number) in played:
                continue
            kept = EpochStore(objects, run_id, number)
            manifest = kept.manifest()
            if manifest.status in _WORKED or manifest.carries_on:
                kept.ask(asked)
