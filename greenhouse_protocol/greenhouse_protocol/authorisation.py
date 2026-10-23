"""Who may do what: authorisation groups, which a run's gateway alone
enforces (decision 0046).

Every planned action carries its principal. A group grants its principals
action kinds, optionally limited to targets: devices, plants, a
controller's targets. A grant may also let its principals propose actions
on behalf of others, as a platform proposing for its users does, and
revise or cancel plans other principals gave. Grants go no further: limits
by time or quantity are a business's rules, which a platform enforces
before it submits.

The configuration has a version, and is an input of the run: the gateway
records which version was in force when, so that a replay decides the
same. Executors and sensors hold no rights. Where the groups live, a
platform or a site's own configuration, is the deployment's.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from greenhouse_protocol.actions import Action, ActionKind, Identifier, targets_of
from greenhouse_protocol.plan import Principal


# A set's order follows its members' hashes, which a string's vary from one
# process to the next: written in order, the same record is the same bytes.
def _sorted_names(names: frozenset[str] | None) -> list[str] | None:
    return None if names is None else sorted(names)


def _sorted_principals(principals: frozenset[Principal]) -> list[Principal]:
    return sorted(principals, key=lambda principal: (principal.kind, principal.id))


class TargetSelector(BaseModel):
    """The targets a grant is limited to, by kind of target: an action's
    devices must all be among `devices`, its plants among `plants`, its
    controller targets among `targets`. A kind left None is not limited."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    devices: frozenset[str] | None = None
    plants: frozenset[str] | None = None
    targets: frozenset[str] | None = None

    @field_serializer("devices", "plants", "targets", when_used="json")
    def _in_order(self, names: frozenset[str] | None) -> list[str] | None:
        return _sorted_names(names)


class Grant(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kinds: frozenset[ActionKind] = frozenset()
    # Every target of those kinds, if None.
    targets: TargetSelector | None = None
    # The principals it may propose actions for, beside its own.
    on_behalf_of: frozenset[Principal] = frozenset()
    # Whether it may revise or cancel plans other principals gave.
    manage_plans: bool = False

    @field_serializer("kinds", when_used="json")
    def _kinds_in_order(self, kinds: frozenset[ActionKind]) -> list[str]:
        return sorted(kinds)

    @field_serializer("on_behalf_of", when_used="json")
    def _principals_in_order(self, principals: frozenset[Principal]) -> list[Principal]:
        return _sorted_principals(principals)

    @model_validator(mode="after")
    def _grants_something(self) -> Self:
        if not (self.kinds or self.on_behalf_of or self.manage_plans):
            raise ValueError("a grant grants kinds, a delegation or managing plans")
        return self

    def allows(self, action: Action) -> bool:
        """Whether this grant lets its principals carry `action` out."""
        if action.kind not in self.kinds:
            return False
        if self.targets is None:
            return True
        acted_on = targets_of(action)
        return all(
            limit is None or names <= limit
            for names, limit in (
                (acted_on.devices, self.targets.devices),
                (acted_on.plants, self.targets.plants),
                (acted_on.targets, self.targets.targets),
            )
        )


class AuthorisationGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group_id: Identifier
    principals: frozenset[Principal]
    grants: tuple[Grant, ...]

    @field_serializer("principals", when_used="json")
    def _principals_in_order(self, principals: frozenset[Principal]) -> list[Principal]:
        return _sorted_principals(principals)


class AuthorisationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[int, Field(ge=1)]
    groups: tuple[AuthorisationGroup, ...]

    @model_validator(mode="after")
    def _groups_named_once(self) -> Self:
        names = [group.group_id for group in self.groups]
        if len(set(names)) != len(names):
            raise ValueError("an authorisation group is named more than once")
        return self

    def grants_of(self, principal: Principal) -> list[Grant]:
        """Every grant of every group the principal is in."""
        return [
            grant
            for group in self.groups
            if principal in group.principals
            for grant in group.grants
        ]

    def allows(self, principal: Principal, action: Action) -> bool:
        """Whether the principal may carry `action` out."""
        return any(grant.allows(action) for grant in self.grants_of(principal))

    def may_propose_for(self, submitter: Principal, principal: Principal) -> bool:
        """Whether an authenticated submitter may give an action proposed by
        `principal`: its own, or one it is granted to propose on behalf of."""
        return submitter == principal or any(
            principal in grant.on_behalf_of for grant in self.grants_of(submitter)
        )

    def may_manage_plans(self, principal: Principal) -> bool:
        """Whether the principal may revise or cancel plans others gave."""
        return any(grant.manage_plans for grant in self.grants_of(principal))
