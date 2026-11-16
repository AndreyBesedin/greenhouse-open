"""An episode's record (P23.2): its digests made one way, and what it
refuses across its fields."""

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from greenhouse_protocol.contracts.gateway import Receipt
from greenhouse_protocol.contracts.policy import CancelPlan, Keep
from greenhouse_protocol.experiment import (
    Condition,
    DecisionTraced,
    Delivered,
    DeliveredLogs,
    EpisodeRun,
    ModelRan,
    ParameterSetRan,
    PolicyEntry,
    PolicyFile,
    PolicyMade,
    WeatherSeries,
    delivered,
    settings_sha256,
)

AT = datetime(2025, 3, 1, tzinfo=UTC)
NOTHING = delivered(())
LOGS = DeliveredLogs(observations=NOTHING, events=NOTHING, outcomes=NOTHING, forecasts=NOTHING)
ENTRY = PolicyEntry(
    factory="policies.band:make",
    settings={"band_c": [15, 17], "weights": "weights.bin"},
    files=("weights",),
    seed=2,
)


def test_the_same_settings_however_written_have_one_digest() -> None:
    assert settings_sha256({"a": 1, "b": [1.5, "x"]}) == settings_sha256({"b": [1.5, "x"], "a": 1})
    assert settings_sha256({"a": 1}) != settings_sha256({"a": 2})
    assert settings_sha256({}) == hashlib.sha256(b"{}").hexdigest()


def test_a_log_delivered_is_counted_and_digested_one_record_a_line() -> None:
    receipts = (Receipt(accepted=True), Receipt(accepted=False, errors=("stale",)))

    logged = delivered(receipts)

    lines = b"".join(receipt.model_dump_json().encode() + b"\n" for receipt in receipts)
    assert logged == Delivered(count=2, sha256=hashlib.sha256(lines).hexdigest())
    assert NOTHING == Delivered(count=0, sha256=hashlib.sha256().hexdigest())


def test_a_policys_files_are_settings_naming_their_paths() -> None:
    with pytest.raises(ValidationError, match="a setting naming its path"):
        PolicyEntry(factory="policies.band:make", settings={"weights": 3}, files=("weights",))
    with pytest.raises(ValidationError, match="a setting naming its path"):
        PolicyEntry(factory="policies.band:make", files=("weights",))


def test_a_policy_made_names_the_digests_of_its_entry() -> None:
    weights = PolicyFile(setting="weights", sha256="0" * 64)
    made = PolicyMade(
        entry=ENTRY, settings_sha256=settings_sha256(ENTRY.settings), files=(weights,)
    )

    assert PolicyMade.model_validate_json(made.model_dump_json()) == made
    with pytest.raises(ValidationError, match="not that of its settings"):
        PolicyMade(entry=ENTRY, settings_sha256="0" * 64, files=(weights,))
    with pytest.raises(ValidationError, match="those its entry names"):
        PolicyMade(entry=ENTRY, settings_sha256=settings_sha256(ENTRY.settings))


def test_only_a_change_given_has_a_receipt() -> None:
    receipt = Receipt(accepted=True, plan_id="policy", revision=1)

    def traced(decision: Keep | CancelPlan, *, skipped: bool) -> DecisionTraced:
        return DecisionTraced(
            at=AT, delivered=LOGS, decision=decision, receipt=receipt, took_s=0.1, skipped=skipped
        )

    assert traced(CancelPlan(), skipped=False).receipt == receipt
    with pytest.raises(ValidationError, match="has no receipt"):
        traced(Keep(), skipped=False)
    with pytest.raises(ValidationError, match="has no receipt"):
        traced(CancelPlan(), skipped=True)


def test_an_episode_ends_within_its_run() -> None:
    with pytest.raises(ValidationError, match="ends within its run"):
        EpisodeRun(
            scenario_id="climate_box",
            greenhouse_id="climate_box",
            layout="default",
            scenario_file_digest=None,
            run_id="climate_box-climate-0",
            epoch=0,
            condition=Condition(duration_days=1),
            seed=7,
            start=AT,
            duration_s=86_400.0,
            episode_end_s=86_401.0,
            models=(),
            weather=WeatherSeries(every_s=600.0, sha256="0" * 64),
        )


def test_a_model_written_before_sets_were_named_reads_with_none() -> None:
    written = ModelRan.model_validate_json('{"part": "crop", "model": "simple", "version": 1}')
    grown = ParameterSetRan(name="gnvman", version=1, digest="sha256:2c83", made_for=1)

    assert written.parameter_set is None
    with_set = written.model_copy(update={"parameter_set": grown})
    assert ModelRan.model_validate_json(with_set.model_dump_json()) == with_set
