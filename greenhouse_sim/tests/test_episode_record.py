"""An episode's record, as the runner builds it (P23.2): the run, the
policy, the software and the trace by decision, from the same episode as its
summary, whose digest it keeps."""

import hashlib
import platform
import sys
from collections.abc import Iterator
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import OBSERVATIONS_ONLY, InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import (
    Decision,
    Delivery,
    Keep,
    PolicyIdentity,
    Revise,
)
from greenhouse_protocol.experiment import (
    EpisodePlace,
    EpisodeRecord,
    delivered,
    settings_sha256,
)
from greenhouse_protocol.plan import Asap, PlannedAction, Principal, PrincipalKind
from pydantic import JsonValue

from greenhouse_sim.experiment import (
    Condition,
    Episode,
    PolicyEntry,
    record_episode,
    run_episode,
)
from greenhouse_sim.scenarios.registry import models_run
from greenhouse_sim.services.run_store import FolderStore
from greenhouse_sim.services.scenario_files import carry
from greenhouse_sim.services.scenarios import scenario, with_weather
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import DAY_S, HOUR_S

sys.path.insert(0, str(Path(__file__).parent))

import short_runs

SCENARIO: Final = "airflow_box"
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="doors")
AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="policies",
            principals=frozenset({POLICY}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
    ),
)
CONDITION: Final = Condition(seed=7, weather="cold_spring_day", duration_days=1)
SIX_HOURS_S: Final = 6 * HOUR_S


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    with Simulator(authorisation=AUTHORISATION) as made:
        yield made


class _Doors:
    """Opens its first door to `level` at each decision, every hour, or
    keeps its plan if `level` is none; keeps what it was given."""

    identity: Final = PolicyIdentity(name="doors", version="1")
    decide_every_s: Final = HOUR_S

    def __init__(self, settings: dict[str, JsonValue], seed: int | None = None) -> None:
        level = settings.get("level")
        assert level is None or isinstance(level, float)
        self._level = level
        self.deliveries: list[Delivery] = []

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self._door = min(device.device_id for device in context.devices)
        self._principal = context.principal

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        self.deliveries.append(delivered)
        if self._level is None:
            return Keep()
        action = SetLevel(device_id=self._door, level=self._level)
        return Revise(
            actions=(
                PlannedAction(
                    action_id=f"door_{len(self.deliveries)}",
                    action=action,
                    timing=Asap(),
                    proposed_by=self._principal,
                ),
            )
        )

    def stop(self) -> None: ...


# The policy an entry made last, to read what it was given.
MADE: list[_Doors] = []


def _kept_doors(settings: dict[str, JsonValue], seed: int | None) -> _Doors:
    MADE.append(_Doors(settings, seed))
    return MADE[-1]


def _episode(
    policy: _Doors | PolicyEntry, condition: Condition = CONDITION, **fields: object
) -> Episode:
    return Episode(
        scenario_id=SCENARIO,
        policy=policy,
        principal=POLICY,
        end_s=SIX_HOURS_S,
        condition=condition,
        **fields,  # type: ignore[arg-type]
    )


def test_a_record_names_its_run_its_policy_its_software_and_each_decision(
    simulator: Simulator, tmp_path: Path
) -> None:
    weights = tmp_path / "weights.bin"
    weights.write_bytes(b"\x00\x01weights")
    entry = PolicyEntry(
        factory=f"{__name__}:_kept_doors",
        settings={"level": 0.5, "weights": str(weights)},
        files=("weights",),
        seed=3,
    )
    place = EpisodePlace(experiment_id="doors", condition=1, policy=0)
    ticks = iter(float(tick) for tick in range(1000))

    record = record_episode(simulator, _episode(entry), place=place, timer=lambda: next(ticks) / 2)

    summary = run_episode(simulator, _episode(_Doors({"level": 0.5})))
    # It reads back from its JSON as it is, and keeps its summary's digest.
    assert EpisodeRecord.model_validate_json(record.model_dump_json()) == record
    assert (record.place, record.digest, record.outcomes) == (
        place,
        summary.digest,
        summary.outcomes,
    )
    run = record.run
    assert (run.scenario_id, run.greenhouse_id, run.layout, run.scenario_file_digest) == (
        SCENARIO,
        SCENARIO,
        "default",
        None,
    )
    assert (run.run_id, run.condition, run.seed, run.duration_s, run.episode_end_s) == (
        summary.run_id,
        CONDITION,
        7,
        DAY_S,
        SIX_HOURS_S,
    )
    under = models_run(with_weather(scenario(simulator.catalogue, SCENARIO), "cold_spring_day"))
    assert {m.part: (m.model, m.version) for m in run.models} == {
        part.value: (ran.model, ran.version) for part, ran in under.items()
    }
    policy = record.policy
    assert policy.made is not None
    assert policy.made.entry.model_dump() == entry.model_dump()
    assert policy.made.settings_sha256 == settings_sha256(entry.settings)
    assert [(f.setting, f.sha256) for f in policy.made.files] == [
        ("weights", hashlib.sha256(weights.read_bytes()).hexdigest())
    ]
    assert (policy.identity, policy.principal, policy.decide_every_s, policy.plan_id) == (
        _Doors.identity,
        POLICY,
        HOUR_S,
        "policy",
    )
    assert (policy.budget, policy.compute_budget_s) == (OBSERVATIONS_ONLY, None)
    software = record.software
    assert (software.producer_version, software.protocol_version, software.python) == (
        version("greenhouse-sim"),
        version("greenhouse-protocol"),
        platform.python_version(),
    )
    # Each decision: when, what each log delivered, what it gave and its
    # receipt, and its time on the runner's timer.
    given = MADE[-1].deliveries
    assert len(record.trace) == summary.decisions == len(given) == 7
    assert [traced.receipt for traced in record.trace] == [g.receipt for g in summary.given]
    assert [traced.at for traced in record.trace] == [g.at for g in summary.given]
    for traced, delivery in zip(record.trace, given, strict=True):
        assert traced.delivered.observations == delivered(delivery.observations)
        assert traced.delivered.outcomes == delivered(delivery.outcomes)
        assert isinstance(traced.decision, Revise)
        assert (traced.took_s, traced.skipped) == (0.5, False)
    assert sum(t.delivered.outcomes.count for t in record.trace) == 6


def test_two_episodes_on_one_condition_share_their_run_and_their_weather(
    simulator: Simulator,
) -> None:
    opened = record_episode(simulator, _episode(_Doors({"level": 1.0})))
    kept = record_episode(simulator, _episode(_Doors({})))
    elsewhere = record_episode(
        simulator, _episode(_Doors({}), condition=Condition(weather="hot_dry_summer_day"))
    )

    assert (opened.run.run_id, opened.run.weather) == (kept.run.run_id, kept.run.weather)
    assert opened.digest != kept.digest
    assert elsewhere.run.weather.sha256 != kept.run.weather.sha256
    assert elsewhere.run.run_id != kept.run.run_id
    # A policy given made already has no entry; one kept made no change.
    assert kept.policy.made is None
    assert all(isinstance(t.decision, Keep) and t.receipt is None for t in kept.trace)


def test_a_decision_past_its_budget_is_traced_skipped_with_no_receipt(
    simulator: Simulator,
) -> None:
    ticks = iter(float(tick) for tick in range(1000))

    record = record_episode(
        simulator,
        _episode(_Doors({"level": 1.0}), compute_budget_s=0.5),
        timer=lambda: next(ticks),
    )

    assert record.policy.compute_budget_s == 0.5
    assert [(t.skipped, t.receipt, t.took_s) for t in record.trace] == [(True, None, 1.0)] * 7
    assert all(isinstance(t.decision, Revise) for t in record.trace)


def test_a_policys_file_that_cannot_be_read_is_refused_before_it_starts(
    simulator: Simulator, tmp_path: Path
) -> None:
    entry = PolicyEntry(
        factory=f"{__name__}:_kept_doors",
        settings={"weights": str(tmp_path / "missing.bin")},
        files=("weights",),
    )
    made = len(MADE)

    with pytest.raises(ValueError, match="the policy's file weights cannot be read"):
        record_episode(simulator, _episode(entry))
    assert len(MADE) == made


def test_a_scenario_not_packaged_is_named_by_its_files_digest(tmp_path: Path) -> None:
    with Simulator(authorisation=AUTHORISATION) as fresh:
        fresh.catalogue.register(short_runs.one_plant_box("recorded_box", 1))

        record = record_episode(
            fresh,
            Episode(scenario_id="recorded_box", policy=_Doors({}), principal=POLICY, end_s=HOUR_S),
        )

        kept = carry(fresh.catalogue, FolderStore(tmp_path), "recorded_box")
    assert kept is not None and record.run.scenario_file_digest == kept
