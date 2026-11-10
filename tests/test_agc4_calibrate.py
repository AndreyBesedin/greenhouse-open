"""Decision 0076's calibration run, from a manifest, and the calibrated
reports committed beside the manifests. No data needed."""

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters
from pydantic import BaseModel

from research.validation.agc4 import calibrate
from research.validation.agc4.calibration import TOMGRO, VANTHOOR, Model, Target
from research.validation.agc4.drivers import DAYS, Hour
from research.validation.agc4.harness import Midnight, Transplant

AGC4 = Path(__file__).resolve().parents[1] / "research/validation/agc4"
TRANSPLANT = Transplant(dry_leaves_g=0.068, dry_stem_g=0.043, leaf_area_cm2=35.1, leaves=5.0)
ON = date(2023, 9, 18)


def _manifest(*parameters: tuple[str, float, float]) -> dict[str, Any]:
    return {
        "model": "toy",
        "method": {
            "optimizer": "scipy.optimize.minimize, method Powell, scipy 1.18.1",
            "options": {"xtol": 1e-6, "ftol": 1e-9, "maxfev": 400},
        },
        "parameters": [{"name": n, "bounds": [low, high]} for n, low, high in parameters],
    }


def _toy(parameters: BaseModel, transplant: Transplant, hours: Sequence[Any]) -> list[Midnight]:
    """A crop whose dry weight is ten times qe and its fruit alpha_f."""
    p = TomgroParameters.model_validate(parameters.model_dump())
    at = datetime(2023, 9, 18, tzinfo=DAYS)
    return [Midnight(at, 48.0, p.alpha_f, 10 * p.qe, 1.0)]


TOY = Model("toy", ("dry_weight_g", "fruit_dry_g"), TomgroParameters(), _toy)


def _target(quantity: str, mean: float, standard_error: float | None = 0.01) -> Target:
    return Target("high", "EC3", ON, quantity, mean, standard_error, 6)


def test_a_parameter_is_scaled_from_its_bounds_and_back() -> None:
    manifest = _manifest(("qe", 0.04, 0.1), ("n_ff", 6.0, 22.0))

    shares = calibrate.scaled(manifest, {"qe": 0.07, "n_ff": 30.0})

    # Beyond its bounds, a start is held at the nearer.
    assert shares == pytest.approx([0.5, 1.0])
    assert calibrate.unscaled(manifest, shares) == pytest.approx({"qe": 0.07, "n_ff": 22.0})


def test_the_calibration_finds_the_parameters_its_targets_ask() -> None:
    manifest = _manifest(("qe", 0.04, 0.1), ("alpha_f", 0.4, 1.0))
    goals = [_target("dry_weight_g", 0.6), _target("fruit_dry_g", 0.55)]

    report = calibrate.calibrate(TOY, manifest, TRANSPLANT, {"high": []}, goals)

    found = {p["name"]: p for p in report["parameters"]}
    assert found["qe"]["calibrated"] == pytest.approx(0.06, rel=1e-3)
    assert found["alpha_f"]["calibrated"] == pytest.approx(0.55, rel=1e-3)
    assert found["qe"]["published"] == 0.08
    assert report["objective"]["calibrated"] < report["objective"]["published"]
    assert report["optimizer"]["method"] == "Powell"
    assert all(row["within_two_se"] for row in report["fit"])


def test_a_parameter_its_targets_push_past_its_bounds_says_so() -> None:
    manifest = _manifest(("qe", 0.04, 0.1))

    dry_weight_alone = replace(TOY, quantities=("dry_weight_g",))

    report = calibrate.calibrate(
        dry_weight_alone, manifest, TRANSPLANT, {"high": []}, [_target("dry_weight_g", 2.0)]
    )

    (qe,) = report["parameters"]
    assert qe["calibrated"] == pytest.approx(0.1)
    assert qe["at_bound"] == "upper"


def test_a_manifest_runs_its_own_model_alone() -> None:
    manifest = _manifest(("qe", 0.04, 0.1)) | {"model": "vanthoor_katzin"}

    with pytest.raises(ValueError, match="vanthoor_katzin's, not toy's"):
        calibrate.calibrate(TOY, manifest, TRANSPLANT, {"high": []}, [])


def test_a_target_measured_as_zero_has_no_relative_error() -> None:
    goals = [
        _target("fruit_dry_g", 0.0, 0.0),
        replace(_target("fruit_dry_g", 0.4), ec="EC5"),
        _target("dry_weight_g", 0.5, 0.05),
    ]

    found = calibrate.fit(TOY, TomgroParameters(), TRANSPLANT, {"high": []}, goals)

    zero, _, dry = found["fit"]
    assert zero["relative_error"] is None
    # Every plant weighed none: no spread to judge an error by.
    assert zero["within_two_se"] is None
    assert dry["error"] == pytest.approx(0.3)
    assert dry["relative_error"] == pytest.approx(0.6)
    assert dry["within_two_se"] is False
    fruit = found["per_quantity"][1]
    assert (fruit["targets"], fruit["relative_errors_of"]) == (2, 1)
    assert fruit["bias"] == pytest.approx((0.8 - 0.4) / 0.4)


def test_a_series_not_the_one_recorded_is_refused(tmp_path: Path) -> None:
    recorded = json.loads(calibrate.DRIVERS.read_text())["wur_agc4-pretrial-2023"]["series"]
    for zone in recorded.values():
        (tmp_path / zone["file"]).write_text("hour_start\n")

    with pytest.raises(ValueError, match=r"not the series drivers\.json records"):
        calibrate.zones(tmp_path)


def test_the_report_is_written_an_item_to_a_line() -> None:
    report = {"model": "toy", "optimizer": {"method": "Powell"}, "fit": [{"a": 1}, {"a": 2}]}

    text = calibrate.written(report)

    assert json.loads(text) == report
    assert text.splitlines() == [
        "{",
        ' "model": "toy",',
        ' "optimizer": {"method": "Powell"},',
        ' "fit": [',
        '  {"a": 1},',
        '  {"a": 2}',
        " ]",
        "}",
    ]


@pytest.mark.parametrize("model", sorted(calibrate.MODELS))
def test_a_committed_calibration_is_its_manifests(model: str) -> None:
    manifest = json.loads((AGC4 / "manifests" / f"{model}.json").read_text())
    report = json.loads((AGC4 / "calibrated" / f"{model}.json").read_text())

    assert report["model"] == manifest["model"] == model
    assert report["decision"] == manifest["decision"]
    assert report["optimizer"]["options"] == manifest["method"]["options"]
    assert report["software"]["scipy"] in manifest["method"]["optimizer"]
    named = [(p["name"], p["published"], p["bounds"]) for p in manifest["parameters"]]
    assert [(p["name"], p["published"], p["bounds"]) for p in report["parameters"]] == named
    for each in report["parameters"]:
        low, high = each["bounds"]
        assert low <= each["calibrated"] <= high
    assert report["objective"]["calibrated"] <= report["objective"]["published"]
    assert sum(q["objective"] for q in report["per_quantity"]) == pytest.approx(
        report["objective"]["calibrated"]
    )
    held = report["per_quantity"]
    assert [q["quantity"] for q in held] == list(calibrate.MODELS[model].quantities)
    assert len(report["fit"]) == sum(q["targets"] for q in held)


def test_the_calibration_reads_its_model_through_the_harness() -> None:
    """The real model, a day of hours: the run the calibration minimises."""
    start = datetime(2023, 9, 18, tzinfo=DAYS)
    hours = [
        Hour(start + timedelta(hours=h), 20.0, 300.0 if 6 <= h < 20 else 0.0, 600.0, 48.0, False)
        for h in range(24)
    ]
    goals = [_target("dry_weight_g", 0.111)]

    found = calibrate.fit(TOMGRO, TomgroParameters(), TRANSPLANT, {"high": hours}, goals)

    (row,) = found["fit"]
    assert row["predicted"] == pytest.approx(0.111)
    assert found["leaves"]["most_leaf_area_index"] == TomgroParameters().lai_max
    assert set(found["leaves"]["largest_leaf_area_index_at_a_midnight"]) == {"high"}
    # Reduced-State TOMGRO prunes nothing.
    assert "pruned_g_per_plant" not in found["leaves"]
    assert [q["quantity"] for q in found["per_quantity"]] == ["dry_weight_g"]


def test_vanthoor_says_what_it_pruned_by_each_date() -> None:
    start = datetime(2023, 9, 18, tzinfo=DAYS)
    hours = [
        Hour(start + timedelta(hours=h), 20.0, 300.0 if 6 <= h < 20 else 0.0, 600.0, 48.0, False)
        for h in range(48)
    ]
    goals = [
        _target("dry_leaves_g", 0.07),
        replace(_target("dry_leaves_g", 0.1), on=ON + timedelta(days=1)),
    ]

    found = calibrate.fit(VANTHOOR, VanthoorParameters(), TRANSPLANT, {"high": hours}, goals)

    pruned = found["leaves"]["pruned_g_per_plant"]["high"]
    assert list(pruned) == ["2023-09-18", "2023-09-19"]
    assert pruned["2023-09-18"] == 0.0
    assert pruned["2023-09-19"] >= 0.0
