"""Sourisseau et al. (2026)'s indoor climate is compared as its manifest
states (research/modelica/sourisseau_2026.json), without Docker: its
windows are the figures' days on the dataset's clock, a reproduction is
within tolerance only at every moment, a day's RMSE is over its own
moments, and both the dataset's files and OpenModelica's results are read
as they are written."""

import datetime as dt
import zipfile
from pathlib import Path

import pytest

from research.modelica import openmodelica as om
from research.modelica import sourisseau_2026 as repro

DAY = om.DAY_S
STEP = om.INTERVAL_S


def test_the_windows_are_the_figures_days_on_the_datasets_clock() -> None:
    # The dataset's clock counts seconds from the start of 2014, in UTC+1,
    # and its season starts the 3rd of December, 2014, as the model's does.
    origin = dt.datetime(2014, 1, 1)
    manifest = repro.manifest()
    assert (
        manifest["ours"]["start_s"]
        == om.START_S
        == (dt.datetime(2014, 12, 3) - origin).total_seconds()
    )
    for name, given in manifest["windows"].items():
        at = repro.window(name)
        start = dt.datetime.fromisoformat(given["from"])
        end = dt.datetime.fromisoformat(given["to"])
        assert (at.start_s, at.end_s) == (
            (start - origin).total_seconds(),
            (end - origin).total_seconds(),
        )
    # The tolerances are those the manifest states, for each variable.
    assert set(repro.VARIABLES) <= set(manifest["tolerances"])


def _flat(value: float, at: repro.Window) -> repro.Series:
    return dict.fromkeys(range(at.start_s - DAY, at.end_s + DAY, STEP), value)


def test_a_reproduction_is_within_tolerance_only_at_every_moment() -> None:
    at = repro.Window("one_day", 10 * DAY, 11 * DAY)
    reference = {"MainAir.T": _flat(290.0, at), "MainAir.RH": _flat(0.7, at)}
    ours = {"MainAir.T": _flat(290.1, at), "MainAir.RH": _flat(0.705, at)}
    measured = {"MainAir.T": _flat(289.0, at), "MainAir.RH": _flat(0.6, at)}
    papers = {"MainAir.T": {at.end_s: 1.0}, "MainAir.RH": {at.end_s: 0.1}}
    tolerances = {"MainAir.T": 0.16, "MainAir.RH": 0.01}

    report = repro.compare(
        ours, reference, measured=measured, papers_daily=papers, at=at, tolerances=tolerances
    )
    found = report["MainAir.T"]
    assert found["within"]
    assert (found["moments"], found["compared"], found["missing"]) == (DAY // STEP + 1,) * 2 + (0,)
    assert found["largest_difference"] == pytest.approx(0.1)
    assert found["rmse_difference"] == pytest.approx(0.1)

    # One moment beyond its tolerance, at the window's last moment: its end
    # is included.
    ours["MainAir.T"][at.end_s] = 290.2
    found = repro.compare(
        ours, reference, measured=measured, papers_daily=papers, at=at, tolerances=tolerances
    )["MainAir.T"]
    assert not found["within"]
    assert (found["beyond_tolerance"], found["first_beyond_s"]) == (1, at.end_s)
    assert found["largest_at_s"] == at.end_s

    # A moment missing from ours is not within either.
    ours["MainAir.T"][at.end_s] = 290.1
    del ours["MainAir.T"][at.start_s + STEP]
    found = repro.compare(
        ours, reference, measured=measured, papers_daily=papers, at=at, tolerances=tolerances
    )["MainAir.T"]
    assert (found["within"], found["missing"]) == (False, 1)


def test_a_days_rmse_is_over_its_moments_from_its_midnight() -> None:
    at = repro.Window("two_days", 10 * DAY, 12 * DAY)
    measured = {"MainAir.T": _flat(289.0, at), "MainAir.RH": _flat(0.6, at)}
    reference = {"MainAir.T": _flat(290.0, at), "MainAir.RH": _flat(0.7, at)}
    ours = {"MainAir.T": _flat(289.5, at), "MainAir.RH": _flat(0.6, at)}
    # The next midnight belongs to the next day: a value there moves only it.
    ours["MainAir.T"][11 * DAY] = 299.5
    papers = {"MainAir.T": {11 * DAY: 1.0, 12 * DAY: 2.0}, "MainAir.RH": {}}
    tolerances = {"MainAir.T": 20.0, "MainAir.RH": 1.0}

    days = repro.compare(
        ours, reference, measured=measured, papers_daily=papers, at=at, tolerances=tolerances
    )["MainAir.T"]["days"]
    assert [day["start_s"] for day in days] == [10 * DAY, 11 * DAY]
    assert days[0]["ours"] == pytest.approx(0.5)
    assert days[1]["ours"] > 0.5
    assert days[0]["papers_series"] == pytest.approx(1.0)
    # The paper's own is stamped with the day's end.
    assert [day["papers_own"] for day in days] == [1.0, 2.0]


def _dataset(path: Path) -> Path:
    series = repro.manifest()["reference"]["series"]
    daily = repro.manifest()["reference"]["daily_rmse"]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            series["member"],
            ",,,,,,,\n"
            "Time,TimeStamp,MainAir.T (K),MainAir.RH (%1),T_inAirProcess_meas (K),"
            "RH_inAirProcess_meas (%1),T_inAirMin_meas (K),T_inAirMax_meas (K)\n"
            "29030400,03:12:2014 00:00:00,293.15,0.51,293.2,0.51,293.2,293.6\n"
            "29030700,03:12:2014 00:05:00,293.0205,0.5091,,0.509,293.3,293.6\n",
        )
        archive.writestr(
            daily["member"],
            "Time,RMSE_T,RMSE_RH,TimeStamp,Season\n29116800,0.683,0.0478,03/12/2014,Autumn\n",
        )
    return path


def test_the_reference_is_read_from_the_datasets_archive(tmp_path: Path) -> None:
    archive = _dataset(tmp_path / "dataset.zip")
    simulated, measured = repro.reference_series(archive)
    assert simulated["MainAir.T"] == {29030400: 293.15, 29030700: 293.0205}
    assert simulated["MainAir.RH"] == {29030400: 0.51, 29030700: 0.5091}
    # A measurement left blank is left out, not read as zero.
    assert measured["MainAir.T"] == {29030400: 293.2}
    assert repro.papers_daily_rmse(archive) == {
        "MainAir.T": {29116800: 0.683},
        "MainAir.RH": {29116800: 0.0478},
    }


def test_our_results_are_read_from_openmodelicas_csv(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    results.write_text(
        '"time","MainAir.RH","MainAir.T"\n2.90304e+07,0.51,293.15\n29030700,0.5,293.0\n'
    )
    assert repro.our_series(results) == {
        "MainAir.T": {29030400: 293.15, 29030700: 293.0},
        "MainAir.RH": {29030400: 0.51, 29030700: 0.5},
    }


def test_a_reproduction_needs_the_dataset_set_up(tmp_path: Path) -> None:
    with pytest.raises(om.PinRefused, match="run `openmodelica setup"):
        repro.reproduce(tmp_path, tmp_path / "work", repro.window("fig8"))
