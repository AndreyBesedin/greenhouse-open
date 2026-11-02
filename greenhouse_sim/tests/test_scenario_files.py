"""The scenario file (P17.11): a manifest in a portable form, written and read
back, and refused, naming the field at fault, when it is not one."""

import json
from collections.abc import Callable, Iterator
from typing import Any, Final

import pytest

from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue, config_digest
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.manifest_files import SCHEMA_VERSION
from greenhouse_sim.scenarios.scenario_files import (
    MAX_IMPORT_BYTES,
    RECORDED_WEATHER,
    ScenarioFileError,
    export_scenario_file,
    import_scenario_file,
)
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import with_weather
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.weather import recorded
from greenhouse_sim.weather.recorded import (
    RECORDED_DIRECTORY,
    RecordedWeather,
    keep_recording,
    recorded_weathers,
    recording_digest,
)

SCENARIO: Final = "climate_box"
CSV: Final = (
    "timestamp,outside_air_temperature_c,outside_relative_humidity_pct\n"
    "2026-04-01T00:00Z,8,90\n2026-04-01T01:00Z,9,85\n"
)


@pytest.fixture(autouse=True)
def _no_recordings_kept(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(recorded, "_KEPT", {})
    yield


def _config(scenario_id: str = SCENARIO) -> ScenarioConfig:
    return PACKAGED.configs[scenario_id]


def _document(config: ScenarioConfig | None = None, **kept: bool) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(export_scenario_file(config or _config(), **kept))
    return document


def _refused(document: dict[str, Any]) -> ScenarioFileError:
    with pytest.raises(ScenarioFileError) as refused:
        import_scenario_file(json.dumps(document))
    return refused.value


def _run_id(config: ScenarioConfig) -> str:
    """The run a scenario's own request gives, in a simulator that knows the
    scenario as `config` is."""
    with Simulator(catalogue=Catalogue(PACKAGED.with_config(config))) as simulator:
        return air_through_a_run(simulator, RunRequest(config.greenhouse_id))[1]


@pytest.mark.parametrize("scenario_id", PACKAGED.ids())
def test_a_packaged_scenario_written_out_and_read_back_is_the_same_scenario(
    scenario_id: str,
) -> None:
    config = _config(scenario_id)
    back = import_scenario_file(export_scenario_file(config))

    assert back.config == config
    assert config_digest(back.config) == config_digest(config)
    assert back.recording is None


@pytest.mark.parametrize("scenario_id", ["climate_box", "airflow_box"])
def test_a_scenario_read_back_gives_the_run_id_of_the_original(scenario_id: str) -> None:
    config = _config(scenario_id)
    back = import_scenario_file(export_scenario_file(config)).config

    assert _run_id(back) == _run_id(config)


def test_a_file_writes_its_layout_out_and_names_the_format() -> None:
    document = _document()

    assert document["schema_version"] == SCHEMA_VERSION
    assert isinstance(document["installation"]["layout"], dict)
    # A scenario's house is its installation's, its models are by part.
    assert "envelope" not in document and "layout" not in document
    assert document["models"]["weather"]["model"] == "constant"


def test_the_same_file_again_is_the_same_scenario() -> None:
    text = export_scenario_file(_config())

    assert import_scenario_file(text).digest == import_scenario_file(text).digest
    changed = export_scenario_file(_config().model_copy(update={"name": "Another name"}))
    assert import_scenario_file(changed).digest != import_scenario_file(text).digest


def test_a_scenario_that_does_not_fill_its_layout_is_not_written() -> None:
    reference = _config("reference_greenhouse")
    fewer = reference.model_copy(update={"rows": reference.rows - 1})

    with pytest.raises(ScenarioFileError, match="cannot be written as a file"):
        export_scenario_file(fewer)


def test_a_recorded_weather_is_carried_with_its_digest() -> None:
    config = with_weather(_config(), "example_day")
    content = (RECORDED_DIRECTORY / "example_day.csv").read_bytes()
    document = _document(config)

    assert document[RECORDED_WEATHER] == {
        "file": "example_day.csv",
        "digest": recording_digest(content),
        "csv": content.decode(),
    }
    back = import_scenario_file(json.dumps(document))
    assert back.config == config
    assert back.recording is not None and back.recording.csv == content
    assert not back.recording_missing


def test_a_recorded_weather_ticked_out_is_named_and_missing_where_it_is_not_offered() -> None:
    keep_recording("mine.csv", CSV.encode())
    config = _config().model_copy(update={"weather": RecordedWeather(file="mine.csv")})
    document = _document(config, with_recording=False)

    assert "csv" not in document[RECORDED_WEATHER]
    assert document[RECORDED_WEATHER]["digest"] == recording_digest(CSV.encode())
    # Where the recording is offered, the file needs nothing else.
    assert not import_scenario_file(json.dumps(document)).recording_missing
    # Where it is not, the scenario cannot be run yet.
    recorded._KEPT.clear()
    missing = import_scenario_file(json.dumps(document))
    assert missing.recording_missing
    assert missing.config == config


def test_a_recording_of_the_same_name_and_other_content_is_not_taken_for_it() -> None:
    keep_recording("mine.csv", CSV.encode())
    config = _config().model_copy(update={"weather": RecordedWeather(file="mine.csv")})
    document = _document(config, with_recording=False)
    document[RECORDED_WEATHER]["digest"] = recording_digest(b"other")

    assert import_scenario_file(json.dumps(document)).recording_missing


def test_a_recording_is_offered_and_kept_under_a_digest_name_on_a_clash() -> None:
    first = keep_recording("mine.csv", CSV.encode())
    assert keep_recording("mine.csv", CSV.encode()) == first == "mine.csv"
    other = CSV.replace(",8,", ",7,").encode()
    second = keep_recording("mine.csv", other)
    packaged = keep_recording("example_day.csv", other)

    assert second == f"mine-{recording_digest(other)[:12]}.csv"
    assert packaged == f"example_day-{recording_digest(other)[:12]}.csv"
    offered = recorded_weathers()
    assert {"example_day", "mine", second.removesuffix(".csv")} <= set(offered)
    assert offered["mine"].identity() == recording_digest(CSV.encode())


@pytest.mark.parametrize("name", ["../mine.csv", "dir/mine.csv", "Mine.csv", "mine.txt", ".csv"])
def test_a_recording_with_a_name_that_is_not_plain_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="not a recording's name"):
        keep_recording(name, CSV.encode())


def test_a_recording_that_is_not_a_weather_file_is_not_kept() -> None:
    with pytest.raises(ValueError, match="a weather file starts with"):
        keep_recording("mine.csv", b"a,b\n1,2\n")
    assert "mine" not in recorded_weathers()


# What a stranger's file may be: each is refused, naming why.


def test_a_file_over_the_limit_is_refused_before_it_is_read() -> None:
    with pytest.raises(ScenarioFileError, match=f"larger than {MAX_IMPORT_BYTES} bytes"):
        import_scenario_file(" " * (MAX_IMPORT_BYTES + 1))


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("not json", "not JSON"),
        ("[]", "not a JSON object"),
        ('{"schema_version": NaN}', "NaN is not a JSON number"),
        ('{"schema_version": 1e999}', "too large a number"),
        ("[" * 100_000, "nested too deeply"),
    ],
)
def test_a_file_that_is_not_json_this_simulator_reads_is_refused(text: str, why: str) -> None:
    with pytest.raises(ScenarioFileError, match=why):
        import_scenario_file(text)


@pytest.mark.parametrize("version", [SCHEMA_VERSION + 1, 6, 0, True, "7", None])
def test_a_file_in_a_format_it_does_not_read_is_refused(version: object) -> None:
    document = _document() | {"schema_version": version}

    refused = _refused(document)
    assert refused.field == "schema_version"
    assert "this simulator reads formats" in refused.message


def _with(document: dict[str, Any], path: list[str], value: object) -> dict[str, Any]:
    changed: dict[str, Any] = json.loads(json.dumps(document))
    target: Any = changed
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return changed


def test_a_field_a_scenario_does_not_have_is_refused_at_any_depth() -> None:
    document = _document()

    assert "fields it does not have: extra" in str(_refused(document | {"extra": 1}))
    layout = _with(document, ["installation", "layout", "extra"], 1)
    assert "installation.layout.extra" in str(_refused(layout))
    envelope = _with(document, ["installation", "envelope", "extra"], 1)
    assert "installation.envelope.extra" in str(_refused(envelope))
    parameters = _with(document, ["models", "weather", "parameters", "extra"], 1)
    assert "models.weather" in str(_refused(parameters))


def test_a_file_with_a_kept_opening_day_is_refused() -> None:
    assert _refused(_document() | {"opening_day": 3}).field == "opening_day"


@pytest.mark.parametrize("scenario_id", ["Bad Name", "../x", "", 3, None])
def test_a_scenario_is_named_by_lowercase_letters_digits_and_underscores(
    scenario_id: object,
) -> None:
    assert _refused(_document() | {"greenhouse_id": scenario_id}).field == "greenhouse_id"


def test_a_layout_that_is_named_and_not_written_is_refused() -> None:
    named = _with(_document(), ["installation", "layout"], "default")

    assert "writes" in str(_refused(named))


def test_a_value_no_greenhouse_can_have_is_refused_naming_its_field() -> None:
    document = _with(_document(), ["duration_days"], -4)

    assert _refused(document).field == "duration_days"


def test_a_recorded_weather_whose_content_is_not_its_digest_is_refused() -> None:
    config = with_weather(_config(), "example_day")
    document = _document(config)
    document[RECORDED_WEATHER]["csv"] = CSV

    refused = _refused(document)
    assert refused.field == f"{RECORDED_WEATHER}.csv"
    assert "not the one the digest names" in refused.message


def test_a_recorded_weather_that_is_not_a_weather_file_is_refused() -> None:
    config = with_weather(_config(), "example_day")
    document = _document(config)
    junk = "a,b\n1,2\n"
    document[RECORDED_WEATHER] |= {"csv": junk, "digest": recording_digest(junk.encode())}

    refused = _refused(document)
    assert refused.field == f"{RECORDED_WEATHER}.csv"
    assert "a weather file starts with" in refused.message


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.pop(RECORDED_WEATHER),
        lambda d: d[RECORDED_WEATHER].update(file="../example_day.csv"),
        lambda d: d[RECORDED_WEATHER].update(file="other.csv"),
        lambda d: d[RECORDED_WEATHER].update(digest="XYZ"),
        lambda d: d[RECORDED_WEATHER].update(extra=1),
        lambda d: d[RECORDED_WEATHER].update(csv=7),
    ],
    ids=["absent", "traversal", "another file", "bad digest", "extra", "csv not text"],
)
def test_a_scenario_under_a_recorded_weather_names_it_wholly_or_is_refused(
    change: Callable[[dict[str, Any]], object],
) -> None:
    document = _document(with_weather(_config(), "example_day"))
    change(document)

    assert RECORDED_WEATHER in _refused(document).field


def test_a_recorded_weather_section_for_another_weather_is_refused() -> None:
    document = _document() | {RECORDED_WEATHER: {"file": "x.csv", "digest": "0" * 64}}

    assert _refused(document).field == RECORDED_WEATHER
