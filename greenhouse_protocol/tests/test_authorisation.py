"""Who may do what (decision 0046): grants by kind and target, delegation,
managing plans, and a configuration written the same way every time."""

import pytest
from pydantic import ValidationError

from greenhouse_protocol.actions import (
    ActionKind,
    Harvest,
    HarvestScope,
    SetLevel,
    SetTarget,
    Water,
)
from greenhouse_protocol.authorisation import (
    AuthorisationConfig,
    AuthorisationGroup,
    Grant,
    TargetSelector,
)
from greenhouse_protocol.plan import Principal, PrincipalKind

GROWER = Principal(kind=PrincipalKind.PERSON, id="grower")
POLICY = Principal(kind=PrincipalKind.POLICY, id="climate")
PLATFORM = Principal(kind=PrincipalKind.PLATFORM, id="platform")
STRANGER = Principal(kind=PrincipalKind.PERSON, id="stranger")


def _config() -> AuthorisationConfig:
    return AuthorisationConfig(
        version=3,
        groups=(
            AuthorisationGroup(
                group_id="climate",
                principals=frozenset({POLICY}),
                grants=(
                    Grant(
                        kinds=frozenset({ActionKind.SET_LEVEL}),
                        targets=TargetSelector(devices=frozenset({"vent_1", "vent_2"})),
                    ),
                    Grant(kinds=frozenset({ActionKind.SET_TARGET})),
                ),
            ),
            AuthorisationGroup(
                group_id="growers",
                principals=frozenset({GROWER}),
                grants=(
                    Grant(
                        kinds=frozenset({ActionKind.HARVEST, ActionKind.WATER}),
                        targets=TargetSelector(plants=frozenset({"p30", "p31"})),
                    ),
                ),
            ),
            AuthorisationGroup(
                group_id="platform",
                principals=frozenset({PLATFORM}),
                grants=(Grant(on_behalf_of=frozenset({GROWER}), manage_plans=True),),
            ),
        ),
    )


def test_a_grant_allows_its_kinds_on_its_targets() -> None:
    config = _config()

    assert config.allows(POLICY, SetLevel(device_id="vent_1", level=1.0))
    assert config.allows(POLICY, SetTarget(target="heating_day", value_c=20))
    assert config.allows(GROWER, Harvest(plant_id="p30", scope=HarvestScope.RIPE))
    assert not config.allows(POLICY, SetLevel(device_id="heater", level=1.0))
    assert not config.allows(GROWER, Water(plant_id="p40", amount_ml=200))
    assert not config.allows(GROWER, SetLevel(device_id="vent_1", level=1.0))
    assert not config.allows(STRANGER, SetLevel(device_id="vent_1", level=1.0))
    assert not config.allows(PLATFORM, Harvest(plant_id="p30", scope=HarvestScope.RIPE))


def test_a_submitter_proposes_for_itself_or_whom_it_is_granted_for() -> None:
    config = _config()

    assert config.may_propose_for(GROWER, GROWER)
    assert config.may_propose_for(PLATFORM, GROWER)
    assert not config.may_propose_for(PLATFORM, POLICY)
    assert not config.may_propose_for(GROWER, POLICY)


def test_managing_others_plans_is_granted() -> None:
    config = _config()

    assert config.may_manage_plans(PLATFORM)
    assert not config.may_manage_plans(GROWER)


def test_a_grant_grants_something() -> None:
    with pytest.raises(ValidationError, match="grants kinds, a delegation or managing plans"):
        Grant()


def test_a_group_is_named_once() -> None:
    group = AuthorisationGroup(
        group_id="g", principals=frozenset({GROWER}), grants=(Grant(manage_plans=True),)
    )

    with pytest.raises(ValidationError, match="more than once"):
        AuthorisationConfig(version=1, groups=(group, group))


def test_a_configuration_is_versioned() -> None:
    with pytest.raises(ValidationError):
        AuthorisationConfig(version=0, groups=())


def test_the_same_configuration_is_the_same_bytes() -> None:
    written = _config().model_dump_json()

    assert AuthorisationConfig.model_validate_json(written) == _config()
    assert written.index('"vent_1"') < written.index('"vent_2"')
    assert written.index('"harvest"') < written.index('"water"')
