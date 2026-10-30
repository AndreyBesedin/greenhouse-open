"""What a client gives and reads of a run's plans (P13.7, decision 0046):
the write side of the gateway contract
(`greenhouse_protocol.contracts.gateway`), served for the runs the
simulator plays back.

A run here is a playback, named by its run's identifier, as the consumer
interface names it (`services.consumer`). A client gives it a plan, or a
revision of one, cancels a whole plan or chosen actions of its plans, lists
the actions not yet resolved, and reads a plan as it stands. Their
outcomes are the consumer interface's to read.

- **Every write is the local operator's** (decision 0052): the local API
  authenticates no one, so a plan's actions are checked against what the
  local operator may do, whoever a document names. No route changes the
  authorisation, which is the server's input.
- **A plan given before a run** is one given to a playback held at its
  start (`playback.start(hold=True)`, the start route's `hold=true`): its
  clock has not moved, and the plan steers its run from there, in its own
  run and epoch.
- **What a gateway refuses** it refuses in its receipt: a write refused
  whole, as stale or beyond its limits, answers `accepted: false` and why,
  and an action refused at once has its outcome. A request that is not one
  is refused before it reaches the gateway, and a run that has finished
  takes nothing more.

What it reaches is a simulator's (decision 0048), as `Acts` names it: the
runs it plays back, and nothing else of it.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Final, Protocol

from greenhouse_protocol.actions import ActionKind, ActionTargets
from greenhouse_protocol.contracts.gateway import ACTUATION_PREFIX, PlanState, Receipt
from greenhouse_protocol.plan import ActionKey, ActionState, ActionStateKind, Plan
from pydantic import TypeAdapter

from greenhouse_sim.services.errors import InvalidRequest, read_as
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.playback import Playback, Playbacks

# Where the gateway's routes live: `/actuation/v1`.
ROUTES_PREFIX: Final = ACTUATION_PREFIX

_KEYS: Final = TypeAdapter(tuple[ActionKey, ...])


class Acts(Protocol):
    """What a client acts on of a simulator: the runs it plays back."""

    @property
    def playbacks(self) -> Playbacks: ...


def give(acts: Acts, run_id: str, body: bytes) -> Receipt:
    """Gives a run's gateway a plan, or a revision of one, as the body
    writes it (`Plan`), as the local operator."""
    plan = read_as("a plan", lambda: Plan.model_validate_json(body))
    return _played(acts, run_id).submit(plan, by=LOCAL_OPERATOR)


def cancel_plan(
    acts: Acts, run_id: str, plan_id: str, *, revision: int | None, epoch: int | None
) -> Receipt:
    """Cancels a whole plan, as its `revision` in `epoch` stood, as the local
    operator: every action of it not started."""
    if revision is None or epoch is None:
        raise InvalidRequest("a plan is cancelled as its revision and epoch stood: give both")
    if revision < 1 or epoch < 0:
        raise InvalidRequest("a revision is 1 or more, and an epoch 0 or more")
    return _played(acts, run_id).cancel_plan(
        plan_id, revision=revision, epoch=epoch, by=LOCAL_OPERATOR
    )


def cancel(acts: Acts, run_id: str, body: bytes) -> Receipt:
    """Cancels chosen actions of a run's plans, by the keys the body lists
    (`ActionKey`, in a JSON array), as the local operator."""
    keys = read_as("a list of action keys", lambda: _KEYS.validate_json(body))
    return _played(acts, run_id).cancel(keys, by=LOCAL_OPERATOR)


def plan(acts: Acts, run_id: str, plan_id: str, revision: int | None = None) -> PlanState:
    """A plan of a run's, as its gateway holds it: its revision in force, or
    `revision`."""
    return _played(acts, run_id).plan(plan_id, revision)


def actions(
    acts: Acts,
    run_id: str,
    *,
    states: Sequence[str] = (),
    kinds: Sequence[str] = (),
    targets: Sequence[str] = (),
    plan_id: str | None = None,
) -> tuple[ActionState, ...]:
    """A run's actions not yet resolved, as they stand by its clock: those
    in any of `states`, of any of `kinds`, acting on any of `targets` (a
    device, a plant or a controller target, by identifier), of `plan_id`;
    each filter unset if none is given."""
    named = frozenset(targets)
    return _played(acts, run_id).actions(
        states=_members(ActionStateKind, states, "state"),
        kinds=_members(ActionKind, kinds, "kind"),
        targets=(ActionTargets(devices=named, plants=named, targets=named) if named else None),
        plan_id=plan_id,
    )


def _played(acts: Acts, run_id: str) -> Playback:
    return acts.playbacks.of_run(run_id)


def _members[E: StrEnum](kind: type[E], given: Sequence[str], name: str) -> frozenset[E] | None:
    """The members of an enumeration `given` names, or None if it names
    none; refused for a name it has not."""
    if not given:
        return None
    known = {member.value: member for member in kind}
    unknown = [value for value in given if value not in known]
    if unknown:
        raise InvalidRequest(
            f"no {name} {unknown[0]!r}: one of {', '.join(sorted(known))}", [(name, unknown[0])]
        )
    return frozenset(known[value] for value in given)
