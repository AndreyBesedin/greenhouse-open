"""How a plant develops organ by organ as thermal time accumulates, and the
plant lab's run, day by day."""

import math
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.tomato.organ import reference
from greenhouse_sim.biology.tomato.organ.development import (
    DevelopmentParams,
    daily_thermal_time,
    develop,
    emerged,
    final_size_fraction,
    grow,
    growth_fraction,
)
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.domain.organs import LeafStage
from greenhouse_sim.scene.snapshot import SceneSnapshot
from greenhouse_sim.services import plants
from greenhouse_sim.services.errors import InvalidRequest

PARAMS = DevelopmentParams()
REFERENCE = plants.ENVIRONMENTS[plants.REFERENCE]


def _rounded(value: object) -> object:
    """A plant's description with its numbers to nine decimals: growth adds
    up step by step, so one step and many agree only to rounding."""
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def _transplant() -> Plant:
    return develop(emerged("p01", PARAMS), plants.TRANSPLANT_CD, PARAMS)


def _leaves(plant: Plant) -> dict[str, tuple[float, LeafStage]]:
    return {p.leaf.leaf_id: (p.leaf.length_cm, p.leaf.stage) for p in plant.stem.phytomers}


def test_a_day_adds_its_mean_temperature_above_the_base_up_to_the_cap() -> None:
    assert daily_thermal_time(21.0, PARAMS) == pytest.approx(11.0)
    assert daily_thermal_time(PARAMS.base_temperature_c, PARAMS) == 0.0
    assert daily_thermal_time(4.0, PARAMS) == 0.0
    assert daily_thermal_time(36.0, PARAMS) == pytest.approx(
        PARAMS.cap_temperature_c - PARAMS.base_temperature_c
    )


def test_a_plant_emerges_with_its_first_phytomer_at_its_initial_size() -> None:
    plant = emerged("p01", PARAMS)
    [first] = plant.stem.phytomers
    scale = final_size_fraction(1, PARAMS)

    assert plant.thermal_time == 0.0 and first.born_tt == 0.0
    assert first.leaf.final_length_cm == pytest.approx(PARAMS.leaf_length_cm * scale)
    assert first.leaf.length_cm == pytest.approx(
        first.leaf.final_length_cm * PARAMS.initial_fraction
    )
    assert first.internode.diameter_mm == pytest.approx(
        first.internode.final_diameter_mm * PARAMS.initial_diameter_fraction
    )
    assert first.leaf.stage == LeafStage.EXPANDING
    assert plant.problems() == []


@pytest.mark.parametrize("thermal_time", [0.0, 32.9, 33.0, 100.0, 230.0, 891.0])
def test_a_phytomer_appears_every_phyllochron(thermal_time: float) -> None:
    plant = develop(emerged("p01", PARAMS), thermal_time, PARAMS)
    phytomers = plant.stem.phytomers

    assert len(phytomers) == math.floor(thermal_time / PARAMS.phyllochron_cd) + 1
    for phytomer in phytomers:
        assert phytomer.born_tt == pytest.approx((phytomer.rank - 1) * PARAMS.phyllochron_cd)


def test_the_labs_plant_has_exact_organ_counts_on_reference_days() -> None:
    """The lab's first plant, drawn from its seed, at the lab's constant
    21 °C, 11 °Cd a day after a transplant of 230 °Cd."""
    counts = {}
    for day in (0, 10, 30, 60):
        plant = plants.structure(plants.LabRun(day=day))
        leaves = [p.leaf for p in plant.stem.phytomers]
        mature = sum(leaf.stage == LeafStage.MATURE for leaf in leaves)
        counts[day] = (plant.thermal_time, len(plant.stem.phytomers), mature)

    assert counts == {
        0: (230.0, 7, 3),
        10: (340.0, 10, 6),
        30: (560.0, 17, 12),
        60: (890.0, 26, 22),
    }


def test_a_plant_grown_in_one_step_or_day_by_day_is_the_same_plant() -> None:
    """In light, CO₂ and water that hold nothing back, whatever the days'
    temperatures."""
    temperatures = [21.0, 18.0, 25.0, 9.0, 31.0, 22.0] * 5
    days = [REFERENCE.model_copy(update={"mean_temperature_c": t}) for t in temperatures]
    total = sum(daily_thermal_time(temperature, PARAMS) for temperature in temperatures)
    daily = grow(_transplant(), days, PARAMS)

    assert _rounded(daily.model_dump(mode="json")) == _rounded(
        develop(_transplant(), total, PARAMS).model_dump(mode="json")
    )


def test_organs_grow_and_mature_but_never_shrink_or_grow_young() -> None:
    plant = _transplant()
    for _ in range(40):
        before = plant
        plant = grow(plant, [REFERENCE], PARAMS)
        old, new = _leaves(before), _leaves(plant)
        for leaf_id, (length, stage) in old.items():
            assert new[leaf_id][0] >= length
            assert not (stage == LeafStage.MATURE and new[leaf_id][1] == LeafStage.EXPANDING)
        for below, above in zip(before.stem.phytomers, plant.stem.phytomers, strict=False):
            assert above.internode.length_cm >= below.internode.length_cm
            assert above.internode.diameter_mm >= below.internode.diameter_mm
            assert above.born_tt == below.born_tt
        assert plant.problems() == []


def test_an_organ_grows_along_an_s_curve_to_its_final_size() -> None:
    initial = PARAMS.initial_fraction
    expansion = PARAMS.expansion_cd
    curve = [growth_fraction(expansion * step / 20, initial, PARAMS) for step in range(21)]

    assert curve[0] == pytest.approx(initial)
    assert curve[10] == pytest.approx((1 + initial) / 2)
    assert curve[-1] == 1.0
    assert growth_fraction(expansion * 3, initial, PARAMS) == 1.0
    gains = [after - before for before, after in zip(curve, curve[1:], strict=False)]
    # Slow, then fast, then slow again.
    assert gains[0] < gains[9] and gains[-1] < gains[10]


def test_a_leaf_matures_when_its_expansion_time_has_passed() -> None:
    plant = develop(emerged("p01", PARAMS), PARAMS.expansion_cd, PARAMS)
    first, second = plant.stem.phytomers[:2]

    assert first.leaf.stage == LeafStage.MATURE
    assert first.leaf.length_cm == pytest.approx(first.leaf.final_length_cm)
    assert second.leaf.stage == LeafStage.EXPANDING
    assert second.leaf.length_cm < second.leaf.final_length_cm


def test_final_sizes_grow_up_the_stem_to_the_full_ones() -> None:
    fractions = [final_size_fraction(rank, PARAMS) for rank in range(1, 15)]

    assert fractions[0] == pytest.approx(PARAMS.first_phytomer_fraction)
    assert fractions == sorted(fractions)
    assert fractions[PARAMS.full_size_rank - 1 :] == [1.0] * (15 - PARAMS.full_size_rank)
    plant = develop(emerged("p01", PARAMS), 560.0, PARAMS)
    top = plant.stem.phytomers[-1]
    assert top.leaf.final_length_cm == pytest.approx(PARAMS.leaf_length_cm)
    assert top.internode.final_length_cm == pytest.approx(PARAMS.internode_length_cm)


def test_a_removed_leaf_stays_removed() -> None:
    plant = reference.young_plant("p01")
    first = plant.stem.phytomers[0]
    removed = first.model_copy(
        update={"leaf": first.leaf.model_copy(update={"stage": LeafStage.REMOVED})}
    )
    stem = plant.stem.model_copy(update={"phytomers": (removed, *plant.stem.phytomers[1:])})
    grown = develop(plant.model_copy(update={"stem": stem}), 100.0, PARAMS)

    assert grown.stem.phytomers[0].leaf == removed.leaf
    assert grown.problems() == []


def test_an_organ_keeps_its_identity_from_one_day_to_the_next() -> None:
    earlier, later = (
        plants.structure(plants.LabRun(day=10)),
        plants.structure(plants.LabRun(day=20)),
    )
    born_earlier = {p.phytomer_id: p.born_tt for p in earlier.stem.phytomers}
    born_later = {p.phytomer_id: p.born_tt for p in later.stem.phytomers}

    assert born_earlier.items() <= born_later.items()
    assert len(born_later) > len(born_earlier)


def test_the_lab_shows_its_plant_on_any_day_of_its_run() -> None:
    scene = respond("GET", "/api/plants/scene?day=12")
    structure = respond("GET", "/api/plants/structure?day=12")
    first_day = respond("GET", "/api/plants/scene")

    assert scene.status == structure.status == first_day.status == HTTPStatus.OK
    assert SceneSnapshot.model_validate(scene.body).simulated_day == 12
    assert SceneSnapshot.model_validate(first_day.body).simulated_day == 0
    assert Plant.model_validate(structure.body) == plants.structure(plants.LabRun(day=12))


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("day=91", "the plant lab runs from day 0 to day 90, not day 91"),
        ("day=-1", "the plant lab runs from day 0 to day 90, not day -1"),
        ("day=soon", "day wants a whole number, not 'soon'"),
    ],
)
def test_a_day_outside_the_labs_run_is_refused(query: str, reason: str) -> None:
    for path in ("scene", "structure"):
        response = respond("GET", f"/api/plants/{path}?{query}")
        assert response.status == HTTPStatus.BAD_REQUEST
        assert response.body == {"error": reason}
    with pytest.raises(InvalidRequest):
        plants.structure(plants.LabRun(day=plants.LAST_DAY + 1))
