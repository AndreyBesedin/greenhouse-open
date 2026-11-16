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
from typing import ClassVar, Final

import pytest
from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import OBSERVATIONS_ONLY, InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import Decision, Delivery, Keep, PolicyIdentity, Revise
from greenhouse_protocol.experiment import EpisodePlace, EpisodeRecord, delivered, settings_sha256
from greenhouse_protocol.plan import Asap, PlannedAction, Principal, PrincipalKind
from pydantic import JsonValue

from greenhouse_sim.experiment import Condition, Episode, PolicyEntry, record_episode, run_episode
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
    keeps its plan if `level` is none; keeps what it was given. Each one
    made is kept, to read what it was given."""

    identity: Final = PolicyIdentity(name="doors", version="1")
    decide_every_s: Final = HOUR_S
    made: ClassVar[list[_Doors]] = []

    def __init__(self, settings: dict[str, JsonValue], seed: int | None = None) -> None:
        level = settings.get("level")
        assert level is None or isinstance(level, float)
        self._level = level
        self.deliveries: list[Delivery] = []
        _Doors.made.append(self)

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
        factory=f"{__name__}:_Doors",
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
    assert record.run.model_dump(exclude={"start", "models", "weather"}) == {
        "scenario_id": SCENARIO,
        "greenhouse_id": SCENARIO,
        "layout": "default",
        "scenario_file_digest": None,
        "run_id": summary.run_id,
        "epoch": summary.epoch,
        "condition": CONDITION.model_dump(),
        "seed": 7,
        "duration_s": DAY_S,
        "episode_end_s": SIX_HOURS_S,
    }
    under = models_run(with_weather(scenario(simulator.catalogue, SCENARIO), "cold_spring_day"))
    assert {m.part: (m.model, m.version) for m in record.run.models} == {
        part.value: (ran.model, ran.version) for part, ran in under.items()
    }
    weights_sha256 = hashlib.sha256(weights.read_bytes()).hexdigest()
    assert record.policy.model_dump(exclude={"budget"}) == {
        "identity": _Doors.identity.model_dump(),
        "made": {
            "entry": entry.model_dump(),
            "settings_sha256": settings_sha256(entry.settings),
            "files": ({"setting": "weights", "sha256": weights_sha256},),
        },
        "principal": POLICY.model_dump(),
        "decide_every_s": HOUR_S,
        "plan_id": "policy",
        "compute_budget_s": None,
    }
    assert record.policy.budget == OBSERVATIONS_ONLY
    software = record.software
    assert (software.producer_version, software.protocol_version, software.python) == (
        version("greenhouse-sim"),
        version("greenhouse-protocol"),
        platform.python_version(),
    )
    # Each decision: when, what each log delivered, what it gave and its
    # receipt, and its time on the runner's timer.
    given = _Doors.made[-1].deliveries
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
        factory=f"{__name__}:_Doors",
        settings={"weights": str(tmp_path / "missing.bin")},
        files=("weights",),
    )
    made = len(_Doors.made)

    with pytest.raises(ValueError, match="the policy's file weights cannot be read"):
        record_episode(simulator, _episode(entry))
    assert len(_Doors.made) == made


def test_a_scenario_not_packaged_is_named_by_its_files_digest(tmp_path: Path) -> None:
    with Simulator(authorisation=AUTHORISATION) as fresh:
        fresh.catalogue.register(short_runs.one_plant_box("recorded_box", 1))

        record = record_episode(
            fresh,
            Episode(scenario_id="recorded_box", policy=_Doors({}), principal=POLICY, end_s=HOUR_S),
        )

        kept = carry(fresh.catalogue, FolderStore(tmp_path), "recorded_box")
    assert kept is not None and record.run.scenario_file_digest == kept
