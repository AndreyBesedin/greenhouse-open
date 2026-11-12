"""Decision 0076's test on the 2024 challenge, as a procedure: what it
reads of the fruit, its baseline, its conversion and its measures. No data
needed: the test ran once, on the data, and its committed reports are held
to their own fit and calibration."""

import io
import json
import math
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl
import pytest
from greenhouse_adapters.wur.agc4_challenge_2024.harvest import (
    FinalHarvest,
    HarvestWorkbook,
    RedFruitPlant,
    SampledPlant,
    Sampling,
)

from research.validation.agc4 import calibrate, challenge
from research.validation.agc4.archives import CHALLENGE
from research.validation.agc4.calibration import TOMGRO, VANTHOOR, Model, Target
from research.validation.agc4.challenge import Assumed, Measured
from research.validation.agc4.drivers import DAYS, Hour
from research.validation.agc4.harness import Midnight, Transplant

TRANSPLANT = Transplant(dry_leaves_g=0.068, dry_stem_g=0.043, leaf_area_cm2=35.1, leaves=5.0)
OCTOBER = date(2024, 10, 7)
HARVESTED = date(2024, 11, 15)


def _plant(code: str, fresh: float, red: float | None = None) -> SampledPlant:
    return SampledPlant(code, f"{code}-1", fresh, 10, None, red)


def _workbook() -> HarvestWorkbook:
    return HarvestWorkbook(
        samplings=[
            Sampling(OCTOBER, [_plant("306", 10.0), _plant("306", 14.0), _plant("301", 99.0)]),
        ],
        final_harvests=[
            FinalHarvest(
                "306",
                [_plant("306", 200.0, 150.0), _plant("306", 260.0, 210.0)],
                [RedFruitPlant("306", "306-40", 240.0, None)],
            ),
        ],
    )


def test_a_compartments_fruit_is_its_plants_means_on_their_days() -> None:
    found = challenge.measured(_workbook(), {"3.06": HARVESTED})

    sampled, final, red = found
    assert (sampled.on, sampled.occasion, sampled.quantity) == (
        OCTOBER,
        "sampling",
        "fruit_fresh_g",
    )
    # Another compartment's plant on the same sheet is not this one's.
    assert (sampled.mean, sampled.plants) == (12.0, 2)
    assert sampled.standard_error == pytest.approx(2.0)
    # The final harvest's fruit is over the plants weighed whole ...
    assert (final.on, final.occasion, final.mean, final.plants) == (
        HARVESTED,
        "final harvest",
        230.0,
        2,
    )
    # ... its red fruit over every plant weighed for it.
    assert (red.quantity, red.mean, red.plants) == ("red_fruit_fresh_g", 200.0, 3)


def test_the_fruit_is_read_from_the_archives_harvest_workbook(tmp_path: Path) -> None:
    book = openpyxl.Workbook()
    book.remove(book.worksheets[0])
    sheet = book.create_sheet("Destructive harvest 7-10-24")
    sheet.append(["Plant", "FW", "# tom"])
    sheet.append(["306-1", 12.0, 3])
    written = io.BytesIO()
    book.save(written)
    archive = tmp_path / "challenge.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr("__MACOSX/timeseries/._Harvest.xlsx", b"")
        opened.writestr("timeseries/Harvest.xlsx", written.getvalue())

    (sampling,) = challenge.harvest(archive).samplings

    assert sampling.day == OCTOBER
    assert [p.fresh_weight_g for p in sampling.plants] == [12.0]


def test_a_compartment_with_no_sheet_has_no_measurement() -> None:
    assert challenge.measured(_workbook(), {"3.02": HARVESTED}) == []


def test_a_compartments_harvest_day_begins_where_its_series_ends() -> None:
    last = datetime(2024, 11, 14, 23, tzinfo=DAYS)
    hour = Hour(last, 20.0, 0.0, 600.0, 20.0, False)

    assert challenge.harvest_days({"3.06": [hour]}) == {"3.06": HARVESTED}


def _goal(ec: str, on: date, mean: float, quantity: str = "fruit_dry_g") -> Target:
    return Target("high", ec, on, quantity, mean, 0.1, 6)


def test_the_baseline_is_the_pretrials_ec3_fruit_by_days_since_transplanting() -> None:
    goals = [
        _goal("EC3", date(2023, 9, 18), 0.0),
        _goal("EC3", date(2023, 9, 29), 1.0),
        _goal("EC3", date(2023, 9, 29), 3.0),
        _goal("EC6", date(2023, 9, 29), 50.0),
        _goal("EC3", date(2023, 11, 9), 12.0),
        _goal("EC3", date(2023, 11, 9), 50.0, "dry_weight_g"),
    ]

    knots = challenge.baseline(goals)

    # Transplanted on 4 September 2023: none then, the zones' mean after.
    assert knots == [(0, 0.0), (14, 0.0), (25, 2.0), (66, 12.0)]
    assert challenge.grown(knots, 7) == 0.0
    assert challenge.grown(knots, 45.5) == pytest.approx(7.0)
    # Past its last date, at its last interval's rate.
    assert challenge.grown(knots, 66 + 41) == pytest.approx(22.0)


def test_the_baseline_needs_two_dates() -> None:
    with pytest.raises(ValueError, match="two dates of EC3 fruit"):
        challenge.baseline([_goal("EC3", date(2023, 11, 9), 12.0)])


def _pretrial(tmp_path: Path, plants: list[tuple[datetime, float | None, float | None]]) -> Path:
    book = openpyxl.Workbook()
    book.remove(book.worksheets[0])
    sheet = book.create_sheet("All Data")
    sheet.append(["Sowing date", None, datetime(2023, 8, 15)])
    sheet.append(["Date", "DW fruits (g/plant)", "FW fruits clusters(g/plant)"])
    for plant in plants:
        sheet.append(list(plant))
    written = io.BytesIO()
    book.save(written)
    archive = tmp_path / "pretrial.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr("DestructiveHarvest.xlsx", written.getvalue())
    return archive


def test_the_dry_matter_is_the_pretrials_last_date_mean_per_plant(tmp_path: Path) -> None:
    september, november = datetime(2023, 9, 29), datetime(2023, 11, 9)
    archive = _pretrial(
        tmp_path,
        [
            (september, 1.0, 5.0),
            (november, 2.0, 20.0),
            (november, 3.0, 50.0),
            # Dried heavier than fresh, weighed nothing fresh, not dried: none.
            (november, 9.0, 4.0),
            (november, 0.0, 0.0),
            (november, None, 30.0),
        ],
    )

    fraction, plants = challenge.pretrial_dry_matter(archive)

    assert fraction == pytest.approx((0.1 + 0.06) / 2)
    assert plants == 2


def test_the_red_batches_are_the_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sheets = {
        "Final Harvest 3.02": {"dried": [{"fruit": "red", "dry_matter_percent": 7.0}]},
        "Final Harvest 3.06": {
            "dried": [
                {"fruit": "green", "dry_matter_percent": 8.0},
                {"fruit": "red", "dry_matter_percent": 6.0},
            ]
        },
        "Information": {},
    }
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({CHALLENGE: {"harvest": {"sheets": sheets}}}))
    monkeypatch.setattr(challenge, "PROFILE", profile)

    assert challenge.red_batches() == pytest.approx([0.06, 0.07])


@pytest.mark.parametrize("model", [TOMGRO, VANTHOOR], ids=["tomgro", "vanthoor_katzin"])
def test_a_model_is_tested_with_its_calibrated_parameters(model: Model) -> None:
    found = challenge.calibrated(model)

    manifest = json.loads((calibrate.MANIFESTS / f"{model.name}.json").read_text())
    assert list(found) == [each["name"] for each in manifest["parameters"]]


def _midnight(on: date, fruit: float, mature: float | None = None) -> Midnight:
    return Midnight(
        datetime(on.year, on.month, on.day, tzinfo=DAYS), 20.0, fruit, 2 * fruit, 1.0, mature
    )


def _measured(
    on: date, occasion: str, mean: float, se: float | None, quantity: str = "fruit_fresh_g"
) -> Measured:
    return Measured("3.06", on, occasion, quantity, mean, se, 6)


def test_a_prediction_is_its_dry_fruit_made_fresh_at_its_days_midnight() -> None:
    final_day = date(2024, 11, 12)
    readings = {
        ("3.06", OCTOBER): _midnight(OCTOBER, 1.6),
        ("3.06", OCTOBER + timedelta(days=1)): _midnight(OCTOBER, 2.0),
        ("3.06", final_day): _midnight(final_day, 16.0, 12.0),
    }
    goals = [
        _measured(OCTOBER, "sampling", 25.0, 2.0),
        _measured(final_day, "final harvest", 180.0, 10.0),
        _measured(final_day, "final harvest", 100.0, 5.0, "red_fruit_fresh_g"),
    ]
    knots = [(0, 0.0), (66, 13.2)]

    sampled, final, red = challenge.compared(goals, readings, knots, Assumed(0.08))

    assert sampled["days_after_transplanting"] == 34
    assert sampled["predicted"] == pytest.approx(20.0)
    assert sampled["predicted_the_midnight_after"] == pytest.approx(25.0)
    assert sampled["error"] == pytest.approx(-5.0)
    assert sampled["relative_error"] == pytest.approx(-0.2)
    assert sampled["within_two_se"] is False
    # The baseline is dry, made fresh by the same fraction: 34 days of 0.2 g.
    assert sampled["baseline"] == pytest.approx(0.2 * 34 / 0.08)
    assert final["predicted"] == pytest.approx(200.0)
    assert final["within_two_se"] is True
    # A final harvest's drivers end at its midnight: none after it.
    assert final["predicted_the_midnight_after"] is None
    # Red fruit is held to the mature fruit, with no baseline.
    assert red["predicted"] == pytest.approx(150.0)
    assert red["baseline"] is None

    later = challenge.compared(goals, readings, knots, Assumed(0.08, after=True))
    assert later[0]["predicted"] == pytest.approx(25.0)
    assert later[1]["predicted"] == pytest.approx(200.0)
    carbohydrate = challenge.compared(goals, readings, knots, Assumed(0.08, dry_per_unit=0.75))
    assert carbohydrate[0]["predicted"] == pytest.approx(15.0)
    assert carbohydrate[0]["baseline"] == pytest.approx(sampled["baseline"])


def _row(occasion: str, measured: float, predicted: float, baseline: float) -> dict[str, object]:
    return {
        "occasion": occasion,
        "measured": measured,
        "standard_error": 10.0,
        "predicted": predicted,
        "baseline": baseline,
    }


def test_the_measures_are_decision_0076s() -> None:
    rows = [
        _row("sampling", 100.0, 110.0, 150.0),
        _row("final harvest", 200.0, 150.0, 190.0),
        _row("final harvest", 300.0, 330.0, 190.0),
        _row("final harvest", 250.0, 260.0, 190.0),
    ]

    found = challenge.measures(rows)

    relative = [0.1, -0.25, 0.1, 0.04]
    assert found["bias"] == pytest.approx(sum(relative) / 4)
    assert found["rms_relative_error"] == pytest.approx(math.sqrt(sum(e**2 for e in relative) / 4))
    assert (found["within_two_se"], found["with_a_standard_error"]) == (2, 4)
    assert (found["spearman_final_harvests"], found["final_harvests"]) == (1.0, 3)
    model = 10**2 + 50**2 + 30**2 + 10**2
    base = 50**2 + 10**2 + 110**2 + 60**2
    assert challenge.skill(rows) == pytest.approx(1 - model / base)
    # The baseline gives every final harvest of a day the same: no order.
    assert challenge.measures(rows, "baseline")["spearman_final_harvests"] is None


def _hours(days: int) -> list[Hour]:
    start = datetime(2024, 9, 3, tzinfo=DAYS)
    return [
        Hour(
            start + timedelta(hours=h),
            20.0,
            300.0 if 6 <= h % 24 < 20 else 0.0,
            600.0,
            56.0,
            h == 5,
        )
        for h in range(24 * days)
    ]


@pytest.mark.parametrize("model", [TOMGRO, VANTHOOR], ids=["tomgro", "vanthoor_katzin"])
def test_a_test_reports_its_measures_sensitivities_and_differences(model: Model) -> None:
    series = {"3.06": _hours(2)}
    harvested = challenge.harvest_days(series)["3.06"]
    goals = [
        _measured(date(2024, 9, 3), "sampling", 0.5, 0.1),
        _measured(harvested, "final harvest", 1.0, 0.2),
        _measured(harvested, "final harvest", 0.5, 0.1, "red_fruit_fresh_g"),
    ]

    found = challenge.tested(
        model,
        challenge.calibrated(model),
        TRANSPLANT,
        series,
        goals=goals,
        knots=[(0, 0.0), (14, 0.0), (25, 1.0), (66, 12.0)],
        dry_matter=(0.08, 48),
        batches=[0.06, 0.07],
    )

    assert found["model"] == model.name
    assert found["assumed"] == {
        "fruit_dry_matter": 0.08,
        "of_plants": 48,
        "dry_matter_per_unit": 1.0,
    }
    assert found["fruit"]["compared"] == 2
    assert "skill" in found["fruit"]
    assert found["baseline_fruit"]["compared"] == 2
    assert found["filled_hours"] == {"3.06": ["2024-09-03T05:00:00+01:00"]}
    varied = [each["varied"] for each in found["sensitivities"]]
    assert varied[:4] == [
        "GreenLight's assumed fruit dry matter, 6 %",
        "the lowest dry matter of 2024's red batches",
        "the highest dry matter of 2024's red batches",
        "each sampling at the midnight after",
    ]
    if model is TOMGRO:
        assert found["red_fruit"]["compared"] == 1
        assert len(found["fit"]) == 3
        assert "pruned_g_per_plant" not in found["leaves"]
        assert len(varied) == 4
    else:
        # Vanthoor's model tells no ripeness, and prunes.
        assert "red_fruit" not in found
        assert len(found["fit"]) == 2
        assert list(found["leaves"]["pruned_g_per_plant"]["3.06"]) == ["2024-09-03", "2024-09-05"]
        assert varied[4] == "0.75 g of dry matter per g of carbohydrate"
    assert found["differences"][: len(challenge.SHARED_DIFFERENCES)] == list(
        challenge.SHARED_DIFFERENCES
    )


def test_a_model_is_tested_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(challenge, "TESTED", tmp_path)
    (tmp_path / "tomgro.json").write_text("{}\n")

    with pytest.raises(SystemExit, match="tests a model once"):
        challenge.main(["tomgro", str(tmp_path)])

    assert (tmp_path / "tomgro.json").read_text() == "{}\n"


def test_a_compartments_series_not_the_one_recorded_is_refused(tmp_path: Path) -> None:
    recorded = json.loads(calibrate.DRIVERS.read_text())[CHALLENGE]["series"]
    for compartment in recorded.values():
        (tmp_path / compartment["file"]).write_text("hour_start\n")

    with pytest.raises(ValueError, match=r"not the series drivers\.json records"):
        calibrate.zones(tmp_path, CHALLENGE)


@pytest.mark.parametrize("model", [TOMGRO, VANTHOOR], ids=["tomgro", "vanthoor_katzin"])
def test_a_committed_report_holds_its_calibration_and_its_fits_measures(model: Model) -> None:
    report = json.loads((challenge.TESTED / f"{model.name}.json").read_text())
    assert report["model"] == model.name
    assert report["parameters"] == challenge.calibrated(model)
    fruit = [row for row in report["fit"] if row["quantity"] == challenge.FRUIT_FRESH]
    red = [row for row in report["fit"] if row["quantity"] == challenge.RED_FRUIT_FRESH]
    assert len(fruit) == 24
    assert len(red) == (6 if model is TOMGRO else 0)
    assert report["fruit"] == challenge.measures(fruit) | {"skill": challenge.skill(fruit)}
    assert report["baseline_fruit"] == challenge.measures(fruit, "baseline")
    assert report.get("red_fruit") == (challenge.measures(red) if red else None)
