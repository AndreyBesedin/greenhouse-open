"""An experiment of paired episodes (P23.3): every policy at each of its
seeds on every condition, in the file's order, each episode's record written
with its place, deliveries kept on request, and a record checked by running
its episode again."""

import hashlib
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import Decision, Delivery, PolicyIdentity, Revise
from greenhouse_protocol.experiment import EpisodeRecord, delivered, settings_sha256
from greenhouse_protocol.plan import Asap, PlannedAction, Principal, PrincipalKind
from pydantic import JsonValue, ValidationError

from greenhouse_sim.experiment.__main__ import main
from greenhouse_sim.experiment.paired import Experiment, check_record, run_experiment
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

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
# Two policies on two conditions: the first at two seeds, the second at
# none, so six episodes, the second's deliveries kept.
EXPERIMENT: Final = {
    "experiment_id": "doors",
    "scenario_id": "airflow_box",
    "principal": POLICY.model_dump(mode="json"),
    "end_s": 3 * HOUR_S,
    "conditions": [{}, {"seed": 7, "weather": "cold_spring_day", "duration_days": 1}],
    "policies": [
        {"factory": f"{__name__}:Doors", "settings": {"level": 0.5}, "seeds": [1, 2]},
        {"factory": f"{__name__}:Doors", "settings": {"level": 0.25}},
    ],
    "keep_deliveries": [1],
}


class Doors:
    """Its first door to its level, and its seed's share of what is left,
    at each decision."""

    identity: Final = PolicyIdentity(name="doors", version="1")
    decide_every_s: Final = HOUR_S

    def __init__(self, settings: dict[str, JsonValue], seed: int | None) -> None:
        level = settings["level"]
        assert isinstance(level, float)
        self._level = level + (1.0 - level) * (seed or 0) / 10

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self._door = min(device.device_id for device in context.devices)
        self._principal = context.principal

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        action = SetLevel(device_id=self._door, level=self._level)
        planned = PlannedAction(
            action_id=f"door_{at:%H}", action=action, timing=Asap(), proposed_by=self._principal
        )
        return Revise(actions=(planned,))

    def stop(self) -> None: ...


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    with Simulator(authorisation=AUTHORISATION) as made:
        yield made


@pytest.fixture(scope="module")
def results(simulator: Simulator, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("results")
    run_experiment(simulator, json.dumps(EXPERIMENT).encode(), out, said=lambda _: None)
    return out


def _record(results: Path, number: int) -> EpisodeRecord:
    return EpisodeRecord.model_validate_json((results / "episodes" / f"{number}.json").read_text())


def test_every_policy_at_each_seed_runs_on_every_condition_in_the_files_order(
    results: Path,
) -> None:
    given = (results / "experiment.json").read_bytes()
    assert json.loads(given) == EXPERIMENT
    assert (results / "experiment.sha256").read_text() == (
        f"{hashlib.sha256(given).hexdigest()}  experiment.json\n"
    )
    records = [_record(results, n) for n in range(6)]
    assert not (results / "episodes" / "6.json").exists()
    assert [
        (
            r.place and (r.place.condition, r.place.policy),
            r.policy.made and r.policy.made.entry.seed,
        )
        for r in records
    ] == [((0, 0), 1), ((0, 0), 2), ((0, 1), None), ((1, 0), 1), ((1, 0), 2), ((1, 1), None)]
    # Each condition's episodes share their run and its weather; the
    # conditions differ.
    for paired in (records[:3], records[3:]):
        assert len({(r.run.run_id, r.run.weather) for r in paired}) == 1
        assert len({r.digest for r in paired}) == 3
    assert records[0].run.run_id != records[3].run.run_id
    assert records[3].run.condition.weather == "cold_spring_day"


def test_the_deliveries_kept_are_those_the_record_counts_and_digests(results: Path) -> None:
    lines = (results / "deliveries" / "1.jsonl").read_text().splitlines()
    kept = [Delivery.model_validate_json(line) for line in lines]

    trace = _record(results, 1).trace
    assert len(kept) == len(trace) == 4
    for traced, delivery in zip(trace, kept, strict=True):
        assert traced.delivered.outcomes == delivered(delivery.outcomes)
        assert traced.delivered.observations == delivered(delivery.observations)
    assert sorted(path.name for path in (results / "deliveries").iterdir()) == ["1.jsonl"]


def test_a_record_checked_gives_its_digest_and_one_changed_does_not(
    simulator: Simulator, results: Path
) -> None:
    record = _record(results, 4)

    assert check_record(simulator, record).same
    assert record.policy.made is not None
    entry = record.policy.made.entry.model_copy(update={"settings": {"level": 0.75}})
    made = record.policy.made.model_copy(
        update={"entry": entry, "settings_sha256": settings_sha256(entry.settings)}
    )
    other = record.model_copy(update={"policy": record.policy.model_copy(update={"made": made})})
    checked = check_record(simulator, other)
    assert (checked.same, checked.recorded) == (False, record.digest)


def test_the_commands_run_an_experiment_and_check_its_records(
    results: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    granted = tmp_path / "authorisation.json"
    granted.write_text(AUTHORISATION.model_dump_json())
    record = results / "episodes" / "2.json"
    tampered = tmp_path / "2.json"
    written = json.loads(record.read_text())
    written["policy"]["made"]["entry"]["settings"]["level"] = 0.5
    tampered.write_text(json.dumps(written))
    experiment = tmp_path / "experiment.json"
    experiment.write_text(json.dumps({**EXPERIMENT, "conditions": [{}], "keep_deliveries": []}))

    ran = main(
        ["--authorisation", str(granted), "run", str(experiment), "--out", str(tmp_path / "out")]
    )
    assert ran == 0 and "episode 2: condition 0, policy 1, seed None" in capsys.readouterr().out
    assert main(["--authorisation", str(granted), "check", str(record)]) == 0
    assert "the same digest" in capsys.readouterr().out
    # A record whose settings were changed by hand is not one: it says why.
    assert main(["--authorisation", str(granted), "check", str(tampered)]) == 1
    assert "settings digest is not that of its settings" in capsys.readouterr().err
    # Without the grant its run was given, its doors are not opened again.
    assert main(["check", str(record)]) == 1
    assert "another digest" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("changed", "says"),
    [
        ({"keep_deliveries": [6]}, "has no episode 6"),
        ({"policies": [{"factory": f"{__name__}:Doors", "seeds": [1, 1]}]}, "each its own"),
        ({"conditions": []}, "at least 1"),
    ],
)
def test_an_experiment_that_cannot_be_run_is_refused(changed: dict[str, object], says: str) -> None:
    with pytest.raises(ValidationError, match=says):
        Experiment.model_validate({**EXPERIMENT, **changed})


def test_nothing_is_written_for_a_condition_shorter_than_the_experiment(
    simulator: Simulator, tmp_path: Path
) -> None:
    short = {**EXPERIMENT, "end_s": 2 * 86_400.0}

    with pytest.raises(ValueError, match="condition 1 ends before the experiment's end"):
        run_experiment(simulator, json.dumps(short).encode(), tmp_path / "out")
    assert not (tmp_path / "out").exists()
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "kept").write_text("")
    with pytest.raises(ValueError, match="holds files already"):
        run_experiment(simulator, json.dumps(EXPERIMENT).encode(), tmp_path / "full")
