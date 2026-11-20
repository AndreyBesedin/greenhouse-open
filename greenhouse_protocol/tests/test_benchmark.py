"""A benchmark's measures as definitions, and an episode's scores (P25.1,
decision 0081): each packaged file reads through its schema, its digest is
its JSON's, an episode's scores name each value's definition, and a
benchmark of a class takes only the measures its class allows."""

import hashlib
import json
from importlib.resources import files
from typing import Any

import pytest
from pydantic import ValidationError

from greenhouse_protocol.benchmark import (
    MEASURES_DIR,
    BenchmarkClass,
    BenchmarkNamed,
    EpisodeScores,
    FromMeasures,
    MeasureClass,
    MeasureDefinition,
    MeasureRole,
    MeasureScored,
    NotComparable,
    PricedTerm,
    packaged_measure,
    packaged_measures,
    read_measure,
    refused_by_class,
    scored,
)
from greenhouse_protocol.experiment import Software

FIRST_MEASURES = {
    "heat-given",
    "temperature-outside-band-by-day",
    "hours-temperature-outside-band-by-day",
    "temperature-outside-band-by-night",
    "hours-temperature-outside-band-by-night",
    "humidity-above-limit",
    "hours-humidity-above-limit",
    "device-switches",
    "device-level-hours",
    "actions-by-status",
    "decisions-skipped",
    "decision-time-median",
    "decision-time-largest",
    "priced-score",
    "harvest",
}
SOFTWARE = Software(
    producer="greenhouse-sim",
    producer_version="0.7.0",
    protocol_version="0.7.0",
    python="3.14.0",
    commit=None,
)
BENCHMARK = BenchmarkNamed(name="climate-winter", version=1, digest="b" * 64)
COMPARED, REPORTED = MeasureRole.COMPARED, MeasureRole.REPORTED


def _packaged_files() -> list[Any]:
    folder = files("greenhouse_protocol").joinpath(MEASURES_DIR)
    return sorted(
        (path for path in folder.iterdir() if path.name.endswith(".json")),
        key=lambda path: path.name,
    )


def test_the_first_measures_are_packaged_one_file_a_version() -> None:
    measures = packaged_measures()

    assert {measure.name for measure in measures} == FIRST_MEASURES
    assert {measure.version for measure in measures} == {1}
    assert len(_packaged_files()) == len(measures)
    assert packaged_measure("harvest", 1).measure_class == MeasureClass.CROP
    with pytest.raises(KeyError, match="no packaged measure 'harvest' at version 2"):
        packaged_measure("harvest", 2)


@pytest.mark.parametrize("path", _packaged_files(), ids=lambda path: path.name)
def test_each_file_reads_through_its_schema_and_writes_every_field(path: Any) -> None:
    """A file writes every field of its definition, so that its digest is
    that of the file's own JSON, keys sorted, and a reader can check it
    without the protocol."""
    text = path.read_text(encoding="utf-8")
    definition = read_measure(text)
    written = json.loads(text)

    assert written == definition.model_dump(mode="json")
    canonical = json.dumps(written, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert definition.digest == hashlib.sha256(canonical.encode()).hexdigest()
    assert path.name == f"{definition.name}.v{definition.version}.json"


def test_a_definition_changed_gives_another_digest_and_written_otherwise_the_same() -> None:
    heat = packaged_measure("heat-given", 1)
    reordered = json.dumps(dict(reversed(heat.model_dump(mode="json").items())))

    assert read_measure(reordered).digest == heat.digest
    for change in (
        {"description": heat.description + " "},
        {"version": 2},
        {"unit": "kWh m⁻²"},
        {"leaves_out": "Nothing."},
    ):
        assert heat.model_copy(update=change).digest != heat.digest


def _definition(**fields: object) -> dict[str, object]:
    return {**packaged_measure("temperature-outside-band-by-day", 1).model_dump(), **fields}


@pytest.mark.parametrize(
    "fields, refusal",
    [
        ({"measure_class": "priced"}, "a priced measure, and it alone, weighs"),
        (
            {"source": packaged_measure("priced-score", 1).source.model_dump()},
            "a priced measure, and it alone, weighs",
        ),
        ({"measure_class": "record"}, "a record measure, and it alone"),
        ({"quantile": 0.5}, "a quantile, and it alone"),
        ({"goal": None}, "against a goal's bounds, and it alone"),
        ({"between_samples": None}, "through time, and it alone"),
        ({"per": ["day", "day"]}, "each denominator once"),
        ({"name": "Temperature_by_day"}, "should match pattern"),
        ({"quantile": 1.5, "aggregation": "quantile"}, "less than or equal to 1"),
    ],
)
def test_a_definition_whose_parts_disagree_is_refused(
    fields: dict[str, object], refusal: str
) -> None:
    with pytest.raises(ValidationError, match=refusal):
        MeasureDefinition.model_validate(_definition(**fields))


def test_a_record_measure_is_over_the_whole_episode() -> None:
    skipped = packaged_measure("decisions-skipped", 1).model_dump()

    with pytest.raises(ValidationError, match="over the whole episode"):
        MeasureDefinition.model_validate({**skipped, "window": "after_warm_up"})


def test_a_priced_score_weighs_each_measure_once() -> None:
    priced = packaged_measure("priced-score", 1).model_dump()
    terms = priced["source"]["terms"]

    with pytest.raises(ValidationError, match="weighs each measure once"):
        MeasureDefinition.model_validate(
            {**priced, "source": {"kind": "measures", "terms": [*terms, terms[0]]}}
        )


def test_an_episodes_scores_name_each_values_definition_and_read_back() -> None:
    heat = packaged_measure("heat-given", 1)
    switches = packaged_measure("device-switches", 1)
    scores = EpisodeScores(
        record_digest="a" * 64,
        benchmark=BENCHMARK,
        measures=(
            scored(heat, 12.5),
            scored(switches, 4.0, of="heater"),
            scored(switches, 0.0, of="roof_vents"),
            scored(packaged_measure("harvest", 1), NotComparable(not_comparable="no crop")),
        ),
        software=SOFTWARE,
    )

    assert EpisodeScores.model_validate_json(scores.model_dump_json()) == scores
    assert scores.measures[0] == MeasureScored(
        name="heat-given", version=1, digest=heat.digest, value=12.5
    )
    assert json.loads(scores.model_dump_json())["measures"][3]["value"] == {
        "not_comparable": "no crop"
    }


def test_an_episodes_scores_on_no_benchmark_say_so_and_must_say_it() -> None:
    """Before a benchmark names its measures, an episode is scored on no
    benchmark: its scores write that as null, never leave it out."""
    scores = EpisodeScores(
        record_digest="a" * 64,
        benchmark=None,
        measures=(scored(packaged_measure("heat-given", 1), 0.25),),
        software=SOFTWARE,
    )

    written = json.loads(scores.model_dump_json())
    assert written["benchmark"] is None
    assert EpisodeScores.model_validate_json(scores.model_dump_json()) == scores
    del written["benchmark"]
    with pytest.raises(ValidationError, match="benchmark"):
        EpisodeScores.model_validate(written)


def test_an_episodes_scores_give_one_value_a_measure_and_part_by_one_digest() -> None:
    heat = packaged_measure("heat-given", 1)

    with pytest.raises(ValidationError, match="one value, or one per part"):
        EpisodeScores(
            record_digest="a" * 64,
            benchmark=BENCHMARK,
            measures=(scored(heat, 1.0), scored(heat, 2.0)),
            software=SOFTWARE,
        )
    with pytest.raises(ValidationError, match="named with two digests"):
        EpisodeScores(
            record_digest="a" * 64,
            benchmark=BENCHMARK,
            measures=(
                scored(heat, 1.0, of="a"),
                MeasureScored(name="heat-given", version=1, digest="c" * 64, of="b", value=1.0),
            ),
            software=SOFTWARE,
        )
    with pytest.raises(ValidationError):
        MeasureScored(name="heat-given", version=1, digest=heat.digest, value=float("nan"))


def _first(role_of_harvest: MeasureRole) -> list[tuple[MeasureDefinition, MeasureRole]]:
    return [
        (measure, role_of_harvest if measure.name == "harvest" else COMPARED)
        for measure in packaged_measures()
    ]


def test_a_crop_measure_is_reported_by_a_climate_benchmark_never_compared() -> None:
    assert refused_by_class(BenchmarkClass.CLIMATE, _first(REPORTED)) == ()
    assert refused_by_class(BenchmarkClass.CLIMATE, _first(COMPARED)) == (
        "a climate benchmark does not take 'harvest', of the crop class, as compared",
    )


def test_an_economic_measure_is_refused_by_a_climate_benchmark_even_reported() -> None:
    cost = packaged_measure("heat-given", 1).model_copy(
        update={"name": "fuel-cost", "measure_class": MeasureClass.ECONOMIC}
    )

    assert refused_by_class(BenchmarkClass.CLIMATE, [(cost, REPORTED)]) == (
        "a climate benchmark does not take 'fuel-cost', of the economic class, as reported",
    )


def test_a_priced_score_weighs_only_measures_its_benchmark_names_and_compares() -> None:
    priced = packaged_measure("priced-score", 1)
    harvest = packaged_measure("harvest", 1)
    assert isinstance(priced.source, FromMeasures)
    weighing_harvest = MeasureDefinition.model_validate(
        {
            **priced.model_dump(),
            "source": FromMeasures(
                terms=(*priced.source.terms, PricedTerm(measure=harvest.named, price="tomato"))
            ),
        }
    )
    others = [
        (measure, COMPARED)
        for measure in packaged_measures()
        if measure.name not in {"harvest", "priced-score"}
    ]
    without_heat = [(measure, role) for measure, role in others if measure.name != "heat-given"]

    assert refused_by_class(BenchmarkClass.CLIMATE, [*others, (priced, COMPARED)]) == ()
    assert refused_by_class(BenchmarkClass.CLIMATE, [*without_heat, (priced, COMPARED)]) == (
        "'priced-score' weighs 'heat-given' version 1, which the benchmark does not name",
    )
    assert refused_by_class(
        BenchmarkClass.CLIMATE,
        [*others, (weighing_harvest, COMPARED), (harvest, REPORTED)],
    ) == (
        "'priced-score' weighs 'harvest', of the crop class, which a climate benchmark does"
        " not compare",
    )
