"""The harness that runs a tomato model on AGC4's hours (decision 0076):
its start, its spacing, and its readings per plant. No data needed."""

import io
import zipfile
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
import pytest
from greenhouse_sim.biology.area_contract import StepCourse
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters, TomgroState
from greenhouse_sim.biology.tomato.vanthoor.growth import leaf_pruning
from greenhouse_sim.biology.tomato.vanthoor.parameters import (
    INITIAL_STATE as VANTHOOR_PUBLISHED,
)
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters
from greenhouse_sim.core.vanthoor_crop import VanthoorRung

from research.validation.agc4 import harness
from research.validation.agc4.drivers import DAYS, Hour, Series
from research.validation.agc4.harness import Transplant

TRANSPLANT = Transplant(dry_leaves_g=0.068, dry_stem_g=0.043, leaf_area_cm2=35.1, leaves=5.0)
START = datetime(2024, 9, 3, tzinfo=DAYS)


def _hours(densities: list[float]) -> list[Hour]:
    """A day of hours per density given: a sunlit day over a warm night."""
    hours: list[Hour] = []
    for day, density in enumerate(densities):
        for hour in range(24):
            start = START + timedelta(days=day, hours=hour)
            sunlit = 6 <= hour < 20
            hours.append(
                Hour(
                    start, 22.0 if sunlit else 18.0, 400.0 if sunlit else 0.0, 600.0, density, False
                )
            )
    return hours


def test_tomgro_starts_from_the_transplants_at_the_density_planted() -> None:
    midnights = harness.run_tomgro(TomgroParameters(), TRANSPLANT, _hours([56.0, 56.0]))

    first = midnights[0]
    assert first.at == START
    assert first.plants_per_m2 == 56.0
    assert first.dry_weight_g == pytest.approx(0.111)
    assert first.leaf_area_index == pytest.approx(35.1e-4 * 56)
    assert first.nodes == 5.0
    assert first.fruit_dry_g == first.mature_fruit_dry_g == 0.0
    # A midnight before each day, and the one after the last.
    assert [m.at for m in midnights] == [START + timedelta(days=d) for d in range(3)]
    assert midnights[-1].dry_weight_g > first.dry_weight_g


def test_vanthoor_starts_from_the_transplants_with_the_buffer_it_is_given() -> None:
    midnights = harness.run_vanthoor(
        VanthoorParameters(), TRANSPLANT, _hours([56.0]), buffer_mg_m2=560.0
    )

    first = midnights[0]
    # Leaves, stem and a buffer of 10 mg a plant, as dry matter one for one.
    assert first.dry_weight_g == pytest.approx(0.111 + 0.010)
    assert first.fruit_dry_g == 0.0
    assert first.leaf_area_index == pytest.approx(
        VanthoorParameters().sla * 0.068 * harness.MG_A_G * 56
    )
    assert first.nodes is None and first.mature_fruit_dry_g is None
    assert first.dry_leaves_g == pytest.approx(0.068)
    assert first.dry_stem_g == pytest.approx(0.043)
    assert len(midnights) == 2


def test_a_spacing_leaves_each_plant_what_it_had() -> None:
    tomgro = TomgroState(n=12.0, lai=1.2, w=56.0, wf=5.6, wm=1.4)
    vanthoor = VANTHOOR_PUBLISHED.model_copy(update={"harvested_fruit": 700.0})

    spaced = harness.spaced_tomgro(tomgro, 56.0, 42.0)
    spread = harness.spaced_vanthoor(vanthoor, 56.0, 42.0)

    assert spaced.n == tomgro.n
    for name in ("lai", "w", "wf", "wm"):
        assert getattr(spaced, name) / 42.0 == pytest.approx(getattr(tomgro, name) / 56.0)
    for name in ("c_buf", "c_fruit", "c_leaf", "c_stem", "harvested_fruit"):
        assert getattr(spread, name) / 42.0 == pytest.approx(getattr(vanthoor, name) / 56.0)
    assert (spread.t_can_sum, spread.t_can_24) == (vanthoor.t_can_sum, vanthoor.t_can_24)


def test_a_run_reads_each_midnight_at_the_density_then_in_force() -> None:
    midnights = harness.run_tomgro(TomgroParameters(), TRANSPLANT, _hours([56.0, 42.0]))

    assert [m.plants_per_m2 for m in midnights] == [56.0, 42.0, 42.0]
    # The second midnight is after the spacing; per plant, nothing jumps.
    assert 0 < midnights[1].dry_weight_g < midnights[2].dry_weight_g


def test_vanthoor_fruit_is_what_stands_and_what_was_harvested() -> None:
    state = VANTHOOR_PUBLISHED.model_copy(update={"c_fruit": 20e3, "harvested_fruit": 8e3})

    midnight = harness._vanthoor_midnight(START, state, 20.0, VanthoorParameters())

    assert midnight.fruit_dry_g == pytest.approx((20e3 + 8e3) / 1000 / 20)


def test_a_series_is_whole_days() -> None:
    with pytest.raises(ValueError, match="whole days"):
        harness.run_tomgro(TomgroParameters(), TRANSPLANT, _hours([56.0])[:23])


def test_a_series_is_read_back_as_it_was_written() -> None:
    hours = _hours([56.0])

    assert harness.read_series(Series("3.06", hours).csv_text()) == hours


def test_the_transplants_are_the_mean_of_the_plants_sampled_on_4_september_2023(
    tmp_path: Path,
) -> None:
    book = openpyxl.Workbook()
    book.remove(book.worksheets[0])
    sheet = book.create_sheet(harness.DESTRUCTIVE_SHEET)
    sheet.append(["Sowing date", None, datetime(2023, 8, 15)])
    columns = [
        harness.DATE,
        harness.DRY_LEAVES,
        harness.DRY_STEM,
        harness.LEAF_AREA,
        harness.SHORT_LEAVES,
        harness.LONG_LEAVES,
    ]
    sheet.append(columns)
    sheet.append([datetime(2023, 9, 4), 0.06, 0.04, 30.0, 2, 3])
    sheet.append([datetime(2023, 9, 4), 0.08, 0.05, 40.0, 1, 4])
    sheet.append([datetime(2023, 9, 18), 0.9, 0.5, 300.0, 0, 9])
    written = io.BytesIO()
    book.save(written)
    archive = tmp_path / "pretrial.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr(harness.DESTRUCTIVE_WORKBOOK, written.getvalue())

    transplant = harness.transplants(archive)

    assert transplant.dry_leaves_g == pytest.approx(0.07)
    assert transplant.dry_stem_g == pytest.approx(0.045)
    assert (transplant.leaf_area_cm2, transplant.leaves) == (35.0, 5.0)


def test_tomgro_grows_at_the_density_in_force_whatever_its_published_rho() -> None:
    hours = _hours([56.0, 42.0])

    published = harness.run_tomgro(TomgroParameters(), TRANSPLANT, hours)
    other = harness.run_tomgro(TomgroParameters(ro=1.0), TRANSPLANT, hours)

    assert published == other


def _spaced_at_23(hours: list[Hour]) -> list[Hour]:
    """The hours with the second day's density from 23:00 of the first: a
    summer spacing at local midnight, at the days' fixed offset."""
    return [
        replace(hour, plants_per_m2=42.0) if index >= 23 else hour
        for index, hour in enumerate(hours)
    ]


def test_vanthoor_is_spaced_at_the_hour_the_density_changes() -> None:
    hours = _spaced_at_23(_hours([56.0, 42.0]))
    parameters = VanthoorParameters()
    buffer = parameters.c_buf_min

    midnights = harness.run_vanthoor(parameters, TRANSPLANT, hours, buffer)

    # The same steps by hand: 23 hours at 56 plants per m², the rest at 42.
    rung = VanthoorRung(parameters, harness.CANOPY_HEIGHT_M)
    state = VANTHOOR_PUBLISHED.model_copy(
        update={
            "c_buf": buffer,
            "c_fruit": 0.0,
            "c_leaf": 0.068 * harness.MG_A_G * 56,
            "c_stem": 0.043 * harness.MG_A_G * 56,
            "harvested_fruit": 0.0,
        }
    )
    for index, hour in enumerate(hours):
        if index == 23:
            state = harness.spaced_vanthoor(state, 56.0, 42.0)
        state = rung.live_step(state, StepCourse(hours=(harness._drivers(hour),)))
    assert midnights[1].plants_per_m2 == 42.0
    pruned = midnights[-1].pruned_leaves_g
    assert pruned is not None
    assert midnights[-1] == harness._vanthoor_midnight(
        midnights[-1].at, state, 42.0, parameters, pruned
    )


def test_tomgro_is_spaced_at_the_midnight_of_its_day() -> None:
    """A day is TOMGRO's step: a spacing an hour before midnight waits for it."""
    at_23 = harness.run_tomgro(TomgroParameters(), TRANSPLANT, _spaced_at_23(_hours([56.0, 42.0])))

    assert at_23 == harness.run_tomgro(TomgroParameters(), TRANSPLANT, _hours([56.0, 42.0]))


def test_vanthoor_reads_the_leaves_it_has_pruned_per_plant() -> None:
    """Transplants with leaves short of the most by 15 g m⁻², a leaf area
    index of 2.6: each hour, the mean of the pruning rate at its start and
    at its end, per plant."""
    parameters = VanthoorParameters()
    leaves_mg_m2 = parameters.c_leaf_max - 15e3
    leafy = replace(TRANSPLANT, dry_leaves_g=leaves_mg_m2 / harness.MG_A_G / 56)
    hours = _hours([56.0])

    midnights = harness.run_vanthoor(parameters, leafy, hours, parameters.c_buf_min)

    rung = VanthoorRung(parameters, harness.CANOPY_HEIGHT_M)
    state = VANTHOOR_PUBLISHED.model_copy(
        update={
            "c_buf": parameters.c_buf_min,
            "c_fruit": 0.0,
            "c_leaf": leaves_mg_m2,
            "c_stem": 0.043 * harness.MG_A_G * 56,
            "harvested_fruit": 0.0,
        }
    )
    pruned_mg_m2 = 0.0
    for hour in hours:
        before = leaf_pruning(state.c_leaf, parameters)
        state = rung.live_step(state, StepCourse(hours=(harness._drivers(hour),)))
        pruned_mg_m2 += (before + leaf_pruning(state.c_leaf, parameters)) / 2 * 3600
    pruned = midnights[-1].pruned_leaves_g
    assert midnights[0].pruned_leaves_g == 0.0
    assert pruned == pytest.approx(pruned_mg_m2 / harness.MG_A_G / 56)
    # Short of the most, the smooth switch prunes a share of the leaves a day.
    assert pruned is not None
    assert pruned > 0.01 * leafy.dry_leaves_g


def test_tomgro_prunes_nothing() -> None:
    midnights = harness.run_tomgro(TomgroParameters(), TRANSPLANT, _hours([56.0]))

    assert {m.pruned_leaves_g for m in midnights} == {None}
