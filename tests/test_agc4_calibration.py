"""The 2023 calibration targets, the objective, and the calibration
manifests of decision 0076. No data needed."""

import io
import json
import math
import zipfile
from datetime import date, datetime
from pathlib import Path

import openpyxl
import pytest
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters

from research.validation.agc4 import calibration
from research.validation.agc4.calibration import Target
from research.validation.agc4.drivers import DAYS
from research.validation.agc4.harness import Midnight

MANIFESTS = Path(__file__).resolve().parents[1] / "research/validation/agc4/manifests"
COLUMNS = [
    "Date",
    "Light",
    "EC",
    calibration.DENSITY,
    calibration.LEAF_AREA,
    calibration.WHOLE,
    *(name for pair in calibration.ORGANS.values() for name in pair),
]


def _plant(on: datetime, light: str, **cells: float | None) -> list[object]:
    values: dict[str, object] = {"Date": on, "Light": light, "EC": "EC3", **cells}
    return [values.get(name) for name in COLUMNS]


def _archive(tmp_path: Path, plants: list[list[object]]) -> Path:
    book = openpyxl.Workbook()
    book.remove(book.worksheets[0])
    sheet = book.create_sheet("All Data")
    sheet.append(["Sowing date", None, datetime(2023, 8, 15)])
    sheet.append(COLUMNS)
    for plant in plants:
        sheet.append(plant)
    written = io.BytesIO()
    book.save(written)
    archive = tmp_path / "pretrial.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr("DestructiveHarvest.xlsx", written.getvalue())
    return archive


def _organs(
    leaves: float, stem: float, fruit_fresh: float, fruit_dry: float | None
) -> dict[str, float | None]:
    return {
        "DW leaves (g/plant)": leaves,
        "FW leaves (g/plant)": leaves * 10,
        "DW stem (g/plant)": stem,
        "FW stem (g/plant)": stem * 10,
        "FW fruits clusters(g/plant)": fruit_fresh,
        "DW fruits (g/plant)": fruit_dry,
    }


def test_the_targets_are_each_treatment_and_dates_means_per_plant(tmp_path: Path) -> None:
    september = datetime(2023, 9, 18)
    archive = _archive(
        tmp_path,
        [
            # Transplants: the start, not a target.
            _plant(datetime(2023, 9, 4), "high light", **{calibration.WHOLE: 0.1}),
            _plant(
                september,
                "high light",
                **{calibration.WHOLE: 1.2, calibration.LEAF_AREA: 250.0, calibration.DENSITY: 48},
                **_organs(0.8, 0.4, 0.0, None),
            ),
            _plant(
                september,
                "high light",
                **{calibration.WHOLE: 1.6, calibration.LEAF_AREA: 270.0, calibration.DENSITY: 48},
                **_organs(1.0, 0.6, 0.0, None),
            ),
        ],
    )

    found = {t.quantity: t for t in calibration.targets(archive)}

    assert {t.zone for t in found.values()} == {"high"}
    assert {t.on for t in found.values()} == {date(2023, 9, 18)}
    assert found["dry_weight_g"].mean == pytest.approx(1.4)
    assert found["dry_weight_g"].standard_error == pytest.approx(0.2)
    assert found["dry_weight_g"].plants == 2
    # No fruit set, weighed as nothing fresh: a measured zero.
    assert found["fruit_dry_g"].mean == 0.0
    assert found["dry_leaves_g"].mean == pytest.approx(0.9)
    assert found["leaf_area_index"].mean == pytest.approx(260.0 / 1e4 * 48)


def test_an_organ_dried_heavier_than_fresh_is_no_target_nor_its_plants_total(
    tmp_path: Path,
) -> None:
    september = datetime(2023, 9, 18)
    impossible = _organs(0.8, 0.4, 0.0, None) | {"DW stem (g/plant)": 0.5, "FW stem (g/plant)": 0.3}
    archive = _archive(
        tmp_path,
        [
            _plant(september, "no light", **{calibration.WHOLE: 1.3}, **impossible),
            _plant(
                september, "no light", **{calibration.WHOLE: 1.0}, **_organs(0.6, 0.4, 0.0, None)
            ),
        ],
    )

    found = {t.quantity: t for t in calibration.targets(archive)}

    assert found["dry_stem_g"].plants == 1
    assert found["dry_weight_g"].plants == 1
    assert found["dry_weight_g"].mean == 1.0
    assert found["dry_leaves_g"].plants == 2


def _reading(fruit: float, dry: float) -> Midnight:
    return Midnight(datetime(2023, 9, 18, tzinfo=DAYS), 48.0, fruit, dry, 1.0)


def test_the_objective_takes_zeros_measured_and_predicted() -> None:
    on = date(2023, 9, 18)
    goals = [
        Target("high", "EC3", on, "fruit_dry_g", 0.0, None, 6),
        Target("low", "EC3", on, "fruit_dry_g", 0.4, 0.1, 6),
        Target("high", "EC3", on, "dry_weight_g", 2.0, 0.1, 6),
    ]
    readings = {("high", on): _reading(0.0, 2.0), ("low", on): _reading(0.0, 1.0)}

    value = calibration.objective(readings, goals, ("fruit_dry_g", "dry_weight_g"))

    # Fruit's floor is half its smallest mean above zero, 0.2; the dry
    # weight's is 1.0. The first two targets: a zero met, then 0 against 0.4.
    assert value == pytest.approx(math.log(0.2 / 0.6) ** 2)


def test_the_objective_refuses_a_quantity_its_model_does_not_give() -> None:
    on = date(2023, 9, 18)
    goals = [Target("high", "EC3", on, "nodes", 9.0, None, 6)]

    with pytest.raises(ValueError, match="no nodes"):
        calibration.objective({("high", on): _reading(0.0, 1.0)}, goals, ("nodes",))


def test_the_screen_is_written_a_line_a_target_or_a_parameter() -> None:
    report = {
        "targets": [{"zone": "high", "mean": 1.0}, {"zone": "low", "mean": 2.0}],
        "screens": [{"model": "tomgro", "objective": 3.0, "screened": [{"parameter": "n_ff"}]}],
    }

    text = calibration.report_text(report)

    assert json.loads(text) == report
    assert len(text.splitlines()) == 11


@pytest.mark.parametrize(
    ("manifest", "published", "quantities"),
    [
        ("tomgro.json", TomgroParameters(), calibration.TOMGRO_QUANTITIES),
        ("vanthoor_katzin.json", VanthoorParameters(), calibration.VANTHOOR_QUANTITIES),
    ],
)
def test_a_manifest_names_at_most_four_parameters_each_bounded_about_its_published_value(
    manifest: str, published: TomgroParameters | VanthoorParameters, quantities: tuple[str, ...]
) -> None:
    named = json.loads((MANIFESTS / manifest).read_text())

    assert named["decision"] == "0076"
    assert tuple(named["quantities"]) == quantities
    assert 1 <= len(named["parameters"]) <= 4
    for parameter in named["parameters"]:
        value = getattr(published, parameter["name"])
        low, high = parameter["bounds"]
        assert parameter["published"] == value
        assert low < high
        assert low <= value <= high
        assert parameter["name"] not in calibration.FIXED
        assert parameter["why"]
