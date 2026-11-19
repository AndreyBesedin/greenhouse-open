"""The blockers are taken out of TiGwerLib as their statement has it
(research/modelica/blockers.json), without Docker: each variant extends
TiGwerLib's global model with modifiers alone, all of them together make
`all` without one setting another's twice, the build loads the variant
beside TiGwerLib, and the gap a variant closes is measured from the
baseline's, its interaction with the others left as it is."""

from typing import Any

import pytest

from research.modelica import blockers
from research.modelica import openmodelica as om


def test_each_variant_extends_tigwerlibs_model_with_modifiers_alone() -> None:
    variants = blockers.variants()
    assert set(variants) == {"screens", "crop", "storage", "ground", "sky", "walls", "all"}
    screens = variants["screens"]
    assert screens.model == "CTIFLWithout_screens"
    source = screens.source()
    assert source.splitlines()[1] == f"  extends {om.MODEL}("
    assert "    SC_UScr(y=0),\n    SC_LScr(y=0));" in source
    assert source.rstrip().endswith("end CTIFLWithout_screens;")
    # A modifier, never an equation.
    assert "equation" not in "".join(v.source() for v in variants.values())


def test_all_is_every_single_variants_modifiers_merged() -> None:
    variants = blockers.variants()
    together = variants["all"].modifiers
    for name in blockers.manifest()["variants"]["all"]["of"]:
        for component, values in variants[name].modifiers.items():
            assert {key: together[component][key] for key in values} == values
    # The two that both modify the soil and the south wall are merged into one modifier each.
    assert together["Soil"] == {
        "rho_t1": "17",
        "rho_t2": "24",
        "lambda_t1": "0.01",
        "lambda_t2": "0.022",
    }
    assert set(together["SouthWall"]) == {"rho_wall", "rho_scr", "SkyBlkBodyTempVarInput"}


def test_two_variants_setting_one_value_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    stated: dict[str, Any] = {
        "variants": {
            "a": {"modifiers": {"Floor": "rho=17"}},
            "b": {"modifiers": {"Floor": "rho=18, c_p=1"}},
            "all": {"of": ["a", "b"]},
        }
    }
    monkeypatch.setattr(blockers, "manifest", lambda: stated)
    with pytest.raises(ValueError, match=r"b modifies Floor's \['rho'\] again"):
        blockers.variants()


def test_the_build_loads_a_variant_beside_tigwerlib() -> None:
    script = om._build_script(
        om.START_S + om.DAY_S,
        variables=None,
        output_format="csv",
        model="CTIFLWithout_sky",
        sources=["CTIFLWithout_sky.mo"],
    )
    lines = script.splitlines()
    tigwerlib = next(i for i, line in enumerate(lines) if "/tigwerlib/TiGwerLib/package.mo" in line)
    assert 'loadFile("/work/CTIFLWithout_sky.mo")' in lines[tigwerlib + 1]
    assert lines[tigwerlib + 2].startswith("buildModel(CTIFLWithout_sky, ")
    assert om.results_of("CTIFLWithout_sky")[1] == "CTIFLWithout_sky_res.csv"
    # TiGwerLib's own model, built as it always was.
    assert om._build_script(1, variables=None, output_format="mat").count("loadFile") == 1
    assert om.results_of(om.MODEL) == om.RESULTS


def _report(mean: float, rmse: float, up: tuple[float, float], down: tuple[float, float]) -> Any:
    return {
        "compared": {
            "MainAir.T": {
                "mean_difference": mean,
                "rmse_difference": rmse,
                "sun_up": {"mean_difference": up[0], "rmse_difference": up[1]},
                "sun_down": {"mean_difference": down[0], "rmse_difference": down[1]},
            }
        }
    }


def test_a_blockers_part_is_its_move_from_the_baseline() -> None:
    baseline = _report(-4.0, 5.0, (-2.0, 3.0), (-6.0, 6.0))
    reports = {
        "screens": _report(-3.0, 4.0, (-2.0, 3.0), (-4.0, 4.5)),
        # Taking this one out widens the gap.
        "sky": _report(-4.5, 5.5, (-2.0, 3.0), (-7.0, 7.0)),
        "storage": _report(-2.0, 2.5, (-1.0, 2.0), (-3.0, 3.0)),
        "all": _report(-0.5, 1.5, (0.5, 1.0), (-1.0, 2.0)),
    }
    found = blockers.apportion(baseline, reports)
    screens = found["moves"]["screens"]["all moments"]
    assert screens["rmse_closed"] == pytest.approx(1.0)
    assert screens["mean_moved"] == pytest.approx(1.0)
    assert screens["share_of_mean"] == pytest.approx(0.25)
    assert found["moves"]["sky"]["all moments"]["rmse_closed"] == pytest.approx(-0.5)
    assert found["moves"]["screens"]["sun_down"]["rmse_closed"] == pytest.approx(1.5)
    # Ranked by how far each takes the RMSE down; `all` is not ranked.
    assert found["ranking"] == ["storage", "screens", "sky"]
    # The singles' sum beside the all-at-once move, their difference left
    # as the interaction, nothing rescaled.
    together = found["together"]["all moments: rmse_closed"]
    assert together["sum_of_singles"] == pytest.approx(1.0 - 0.5 + 2.5)
    assert together["all_at_once"] == pytest.approx(3.5)
    assert together["interaction"] == pytest.approx(0.5)
