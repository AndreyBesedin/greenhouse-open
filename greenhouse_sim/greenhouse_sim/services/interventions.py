"""What a change given to an epoch is, as its log writes it (P17.8, decision
0065): a target changed, a plan given, actions or a plan cancelled, in the
gateway's own words, so that applying an entry again is the gateway being
given the same thing.

`Logged` is what a log entry's `what` holds. `Asked` is what someone other than
the epoch's worker asks of it through the store: the same, but for a target
change, whose moment is the worker's to choose, the next minute of the epoch's
clock when it takes the request.
"""

from typing import Annotated, Final, Literal

from greenhouse_protocol.plan import ActionKey, Plan, Principal, PrincipalKind
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from greenhouse_sim.services.runs import Commanded


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
