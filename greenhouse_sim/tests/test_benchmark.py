"""The simulator's benchmark (P09.8): it runs on the reference scenario, its
report has every measure, and the report kept in the repository too."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from greenhouse_sim import benchmark
from greenhouse_sim.core.stopwatch import Stopwatch, timed
from greenhouse_sim.services.benchmark import DayCosts, bottleneck, simulator_costs
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.simulator import Simulator

# The report kept in the repository, beside these tests: CI installs the
# simulator as a package, out of the checkout.
KEPT_REPORT = Path(__file__).resolve().parents[1] / "benchmarks" / "simulator.json"
# What a report says, measure by measure.
MEASURES = {
    "recorded",
    "machine",
    "scenario_id",
    "manifest_version",
    "days",
    "days_s",
    "per_day",
    "season_days",
    "season_s",
    "cell_by_cell_hour_s",
    "frame_scene_s",
    "frame_scene_mib",
    "counts",
    "bottleneck",
    "peak_memory_mib",
}
DAY_PARTS = {"house_air_s", "plants_light_s", "plants_days_s", "total_s"}
COUNTS = {"entities", "organs", "plants", "field_cells", "field_cells_total"}
MACHINE = {"platform", "cpu", "cores", "memory_gib", "python"}


@pytest.fixture(scope="module")
def one_day(simulator: Simulator, afresh_module: Callable[[], None]) -> dict[str, Any]:
    """The benchmark's report on the reference run's first day, worked out
    afresh: nothing another test kept gives the run its days."""
    return benchmark.report(simulator, days=1)


def _has_every_measure(report: dict[str, Any]) -> None:
    assert set(report) == MEASURES
    assert set(report["per_day"]) == DAY_PARTS
    assert set(report["counts"]) == COUNTS
    assert set(report["machine"]) == MACHINE


def test_the_benchmark_runs_on_the_reference_scenario(one_day: dict[str, Any]) -> None:
    _has_every_measure(one_day)
    assert (one_day["scenario_id"], one_day["days"], one_day["season_days"]) == (
        "reference_greenhouse",
        1,
        120,
    )
    per_day = one_day["per_day"]
    # Its parts are timed within the day's whole, each of them spent.
    assert per_day["house_air_s"] > 0 and per_day["plants_light_s"] > 0
    parts = per_day["house_air_s"] + per_day["plants_light_s"] + per_day["plants_days_s"]
    assert parts <= per_day["total_s"]
    assert one_day["season_s"] == pytest.approx(120 * per_day["total_s"], rel=1e-2)
    assert one_day["cell_by_cell_hour_s"] > 0 and one_day["frame_scene_s"] > 0
    counts = one_day["counts"]
    assert counts["plants"] == 32
    assert counts["entities"] > counts["organs"] > 0
    assert counts["field_cells"] == [24, 20, 8] and counts["field_cells_total"] == 3840
    assert one_day["peak_memory_mib"] > 0
    assert "of a simulated day" in one_day["bottleneck"]


def test_the_kept_report_has_every_measure() -> None:
    kept = json.loads(KEPT_REPORT.read_text())

    _has_every_measure(kept)
    # The whole season, from its start, on the machine it names.
    assert (kept["scenario_id"], kept["days"]) == ("reference_greenhouse", kept["season_days"])
    assert kept["machine"]["cpu"]


def test_a_benchmark_measures_days_its_run_has(simulator: Simulator) -> None:
    for days in (0, 121):
        with pytest.raises(InvalidRequest, match="a benchmark measures 1 to 120"):
            simulator_costs(simulator, "reference_greenhouse", days)


def test_the_bottleneck_is_the_costliest_part_of_a_day() -> None:
    said = bottleneck(
        DayCosts(house_air_s=0.4, plants_light_s=1.2, plants_days_s=0.2, total_s=2.0),
        cell_by_cell_hour_s=5.0,
    )

    assert said.startswith("the plants' light: 60% of a simulated day (1.20 s of 2.00 s).")
    assert "kept through a day it would take 120 s, 60 times" in said


def test_the_command_compares_the_latest_report_with_the_kept_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    kept = json.loads(KEPT_REPORT.read_text())
    monkeypatch.setattr(benchmark, "report", lambda simulator, days: kept | {"days": days})
    copy = tmp_path / "simulator.json"
    copy.write_text(KEPT_REPORT.read_text())

    benchmark.main(["--days", "3", "--report", str(copy)])

    said = capsys.readouterr().out
    assert said.startswith("reference_greenhouse, 3 days on ")
    assert f"house_air_s{'':<13}" in said
    assert f"next bottleneck: {kept['bottleneck']}" in said

    # Recorded, the latest is kept where the report is named.
    benchmark.main(["--days", "3", "--report", str(copy), "--record"])
    assert json.loads(copy.read_text())["days"] == 3


def test_without_a_kept_report_the_command_compares_with_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    kept = json.loads(KEPT_REPORT.read_text())
    monkeypatch.setattr(benchmark, "report", lambda simulator, days: kept)
    monkeypatch.setattr(benchmark, "CHECKOUT_REPORT", Path("/nowhere/benchmarks/simulator.json"))

    benchmark.main([])
    assert "(—)" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        benchmark.main(["--record"])


def test_a_stopwatch_adds_up_each_part_and_none_times_nothing() -> None:
    watch = Stopwatch()
    for _ in range(2):
        with timed(watch, "part"):
            pass
    with timed(None, "part"):
        pass

    assert set(watch.seconds) == {"part"}
    assert watch.seconds["part"] >= 0
