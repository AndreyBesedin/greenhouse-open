"""How an approved action reaches whatever carries it out: an executor,
behind a run's gateway (decision 0046).

A decision system decides what should happen. Something else makes it
happen: a simulated world, or in a real deployment a task assigned to a
grower, a climate controller or a robot. Those are interchangeable behind
this one contract, so that decision logic does not know which it is talking
to. The contract belongs to neither side.

Not every environment can execute. Recorded history cannot change, so a
replay adapter refuses rather than pretending, and `ActionNotExecutable` is
how it says so: replay can never execute an action by accident.

An executor carries out one action it is assigned, at an instant, and
reports it (`ActionExecutor`); a run's gateway decides everything else
(`greenhouse_protocol.contracts.gateway`). The channel between them may
lose a message, so an executor carries an assignment out at most once,
whatever number of times it receives it; a gateway may revoke one not yet
started, and ask how one stands when its report does not come. The
channel must be authenticated, each end sure of the other; how is the
deployment's.

`ActionExecutionAdapter` is deprecated (decision 0046): a run's gateway and
its executors replace it. It stays, as it is, until the simulator carries
the new format out.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from greenhouse_protocol.action import RequestedAction
from greenhouse_protocol.actions import ActionKind, ActionRef, Inspect, SetLevel
from greenhouse_protocol.assignment import Assignment, ExecutionReport
from greenhouse_protocol.execution import ActionOutcome


class ActionNotExecutable(Exception):
    """This environment cannot carry actions out at all."""

    def __init__(self, greenhouse_id: str, reason: str) -> None:
        super().__init__(reason)
        self.greenhouse_id = greenhouse_id
        self.reason = reason


class ActionExecutionAdapter(Protocol):
    def execute(
        self, greenhouse_id: str, actions: list[RequestedAction], *, at: datetime
    ) -> list[ActionOutcome]:
        """Validates and carries out each action, in order.

        Returns one outcome per action given, positionally, so a refused
        action keeps its place. Raises `ActionNotExecutable` if the
        environment cannot execute at all, which is a different thing from
        refusing a particular action.
        """
        ...


class Revocation(StrEnum):
    """How an executor answers a revocation."""

    REVOKED = "revoked"  # it had not started, and will not
    STARTED = "started"  # too late: it is under way, and will report
    FINISHED = "finished"  # too late: it is done, and has reported or will
    UNKNOWN = "unknown"  # it never received the assignment


class AssignmentStatus(StrEnum):
    """How an assignment stands at an executor, when a gateway asks."""

    RECEIVED = "received"
    STARTED = "started"
    FINISHED = "finished"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class ActionExecutor(Protocol):
    """Carries out the actions a run's gateway assigns it, and reports them.

    The rules an executor keeps:

    - It carries out only the kinds it names (`kinds`), at the instants it
      says it honours (`honours`), as many at once as its `capacity`.
    - It carries an assignment out at most once. An assignment id received
      again is answered as before and never performed twice, so a gateway
      may send it again when unsure it arrived.
    - It wants an assignment no earlier than its lead time before its
      instant (`lead_time_s`), and takes no longer than its longest duration
      (`longest_duration_s`) to carry one out; past that, a gateway that has
      had no report asks `status`, and resolves the action as unconfirmed if
      the executor cannot be reached.
    - A revoked assignment it had not started is never carried out.
    - It checks the greenhouse when it starts: an action the greenhouse is
      not as needed for (a truss that has not grown) is refused, with why.
    - It holds no rights: whatever reaches it over the gateway's
      authenticated channel was authorised there.
    """

    def kinds(self) -> frozenset[ActionKind]: ...

    def honours(self, kind: ActionKind, instant: datetime) -> bool: ...

    def capacity(self) -> int: ...

    def lead_time_s(self, kind: ActionKind) -> float: ...

    def longest_duration_s(self, kind: ActionKind) -> float: ...

    def perform(self, assignment: Assignment) -> None:
        """Takes an assignment, to start at its instant; idempotent."""
        ...

    def revoke(self, assignment_id: str) -> Revocation: ...

    def status(self, assignment_id: str) -> AssignmentStatus: ...

    def reports(self, after: int = 0) -> Sequence[ExecutionReport]:
        """Its reports after the first `after`, in the order it made them."""
        ...


class ExecutorUnderTest(ActionExecutor, Protocol):
    """An executor, with what a test needs to move its clock."""

    def advance(self, to: datetime) -> None: ...


type MakeExecutor = Callable[[datetime], ExecutorUnderTest]


def check_executor(make: MakeExecutor, start: datetime) -> list[str]:
    """Holds an executor to the contract's rules, each on an executor `make`
    gives for a clock starting at `start`: an assignment sent twice carried
    out at most once, one revoked before it starts never carried out, a
    revocation too late said so, and an unknown assignment said unknown.
    Returns the violations, empty when it conforms."""
    executor = make(start)
    if ActionKind.SET_LEVEL in executor.kinds():
        action: SetLevel | Inspect = SetLevel(device_id="conformance_device", level=1.0)
    else:
        action = Inspect(plant_id="conformance_plant", reason="a conformance check")
    longest = timedelta(seconds=executor.longest_duration_s(action.kind))
    soon = Assignment(
        assignment_id="soon",
        run_id="conformance",
        ref=ActionRef(action_id="soon"),
        action=action,
        at=start + timedelta(minutes=1),
    )
    later = soon.model_copy(
        update={
            "assignment_id": "later",
            "ref": ActionRef(action_id="later"),
            "at": start + timedelta(hours=1),
        }
    )
    violations = []
    # Each sent twice, as a gateway unsure that a message arrived sends it.
    for assignment in (soon, soon, later, later):
        executor.perform(assignment)
    if (revoked := executor.revoke("later")) != Revocation.REVOKED:
        violations.append(f"an assignment revoked before it started was answered {revoked}")
    executor.advance(later.at + longest + timedelta(seconds=1))
    reports = [r.assignment_id for r in executor.reports()]
    if reports.count("soon") > 1:
        violations.append("an assignment sent twice was reported twice")
    if reports.count("soon") == 0 and executor.status("soon") not in {
        AssignmentStatus.STARTED,
        AssignmentStatus.FINISHED,
    }:
        violations.append("an assignment received was neither reported nor said to be under way")
    if "later" in reports or executor.status("later") != AssignmentStatus.REVOKED:
        violations.append("a revoked assignment was carried out")
    if executor.revoke("soon") not in {Revocation.STARTED, Revocation.FINISHED}:
        violations.append("a revocation after an assignment started was not said to be too late")
    if (
        executor.revoke("never") != Revocation.UNKNOWN
        or executor.status("never") != AssignmentStatus.UNKNOWN
    ):
        violations.append("an assignment never received was not said to be unknown")
    return violations
