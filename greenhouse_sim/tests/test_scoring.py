"""An experiment's episodes scored (P25.3, decisions 0081 and 0082): each
episode's scores written beside its record once its policy has stopped,
example 03's rule given the values its instruments give by hand; a record
scored again only when it replays to its digest, and the same scores each
time; and no episode's digest moved by scoring it."""

import json
import shutil
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import ActionKind
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.benchmark import (
    EpisodeScores,
    MeasureValue,
    NotComparable,
    packaged_measure,
    packaged_measures,
)
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import Decision, Delivery, Keep, PolicyIdentity
from greenhouse_protocol.experiment import EpisodeRecord, settings_sha256
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import Principal, PrincipalKind

from greenhouse_sim.evaluation.instruments import Instruments, SetBy
from greenhouse_sim.evaluation.scoring import HARVEST_NOT_COUNTED, score_episode
from greenhouse_sim.experiment import Episode, carry_out_episode
from greenhouse_sim.experiment.__main__ import main
from greenhouse_sim.experiment.paired import Experiment, run_experiment, score_experiment
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

EXAMPLES: Final = Path(__file__).resolve().parents[2] / "examples"
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="naive_heating")
AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="policies",
            principals=frozenset({POLICY}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
    ),
)
END_S: Final = 1800.0
FIRST_BAND: Final = {"on_below_c": 15.0, "off_above_c": 17.0}
SECOND_BAND: Final = {"on_below_c": 17.0, "off_above_c": 19.0}
# Example 06's first condition, the climate box's own still night at seed 1,
# and its two bands: example 03's rule, at example 03's band and two
# degrees above it.
EXPERIMENT: Final = {
    "experiment_id": "heating_bands",
    "scenario_id": "climate_box",
    "principal": POLICY.model_dump(mode="json"),
    "end_s": END_S,
    "conditions": [{"seed": 1}],
    "policies": [
        {"factory": "naive_heating:NaiveHeating", "settings": FIRST_BAND},
        {"factory": "naive_heating:NaiveHeating", "settings": SECOND_BAND},
    ],
}
# The digests example 06 and its guide give these two episodes, written
# before episodes were scored (`docs/guides/run-an-experiment.md`).
GUIDES_DIGESTS: Final = ("3c9248fbd0d61848", "57f9e1f03cd61ebe")
# The climate box's heater, and its floor, 12 m by 6.4 m.
HEATER: Final = "heater"
HEATER_W: Final = 10_000.0
FLOOR_M2: Final = 76.8
DAYS: Final = END_S / 86_400.0

type Values = dict[tuple[str, str | None], MeasureValue]


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    with Simulator(authorisation=AUTHORISATION) as made:
        yield made


@pytest.fixture(scope="module")
def results(simulator: Simulator, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The experiment, run into a folder: its factory, example 03's rule
    made from its band, found beside the examples as example 06 finds it."""
    out = tmp_path_factory.mktemp("results")
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(EXAMPLES))
        run_experiment(simulator, json.dumps(EXPERIMENT).encode(), out, said=lambda _: None)
        yield out


def _record(results: Path, number: int) -> EpisodeRecord:
    return EpisodeRecord.model_validate_json((results / "episodes" / f"{number}.json").read_text())


def _scores(results: Path, number: int) -> EpisodeScores:
    return EpisodeScores.model_validate_json((results / "scores" / f"{number}.json").read_text())


def _values(scores: EpisodeScores) -> Values:
    return {(scored.name, scored.of): scored.value for scored in scores.measures}


def _copied(results: Path, tmp_path: Path) -> Path:
    return Path(shutil.copytree(results, tmp_path / "results"))


def test_each_episode_is_scored_beside_its_record_and_no_digest_moves(results: Path) -> None:
    """Each record keeps the digest it had before episodes were scored, and
    holds no score; its scores, beside it, name it by that digest, every
    packaged measure by its digest, and no benchmark."""
    assert sorted(path.name for path in (results / "scores").iterdir()) == ["0.json", "1.json"]
    for number, digest in enumerate(GUIDES_DIGESTS):
        record = _record(results, number)
        scores = _scores(results, number)
        assert record.digest.startswith(digest)
        assert set(json.loads((results / "episodes" / f"{number}.json").read_text())) == set(
            EpisodeRecord.model_fields
        )
        assert (scores.record_digest, scores.benchmark) == (record.digest, None)
        assert scores.software == record.software
        named = {(scored.name, scored.version, scored.digest) for scored in scores.measures}
        assert named == {(m.name, m.version, m.digest) for m in packaged_measures()}


def test_example_03s_rule_scored_gives_the_values_its_instruments_give_by_hand(
    simulator: Simulator, results: Path
) -> None:
    """At example 03's band on the still night, the rule turns the heater on
    at 5 min, off at 20 and on at 25: 20 of the 30 min, three switches."""
    record = _record(results, 0)
    values = _values(_scores(results, 0))
    episode = next(e for _, e in Experiment.model_validate(EXPERIMENT).episodes())
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(EXAMPLES))
        instruments = Instruments(simulator, carry_out_episode(simulator, episode).run, END_S)
    heater = instruments.equipment[HEATER]

    assert [(state.at_s, state.level, state.set_by) for state in heater] == [
        (0.0, 0.0, SetBy.START),
        (300.0, 1.0, SetBy.COMMAND),
        (1200.0, 0.0, SetBy.COMMAND),
        (1500.0, 1.0, SetBy.COMMAND),
    ]
    on_s = sum(
        (later - state.at_s) * state.level
        for state, later in zip(heater, [*(s.at_s for s in heater[1:]), END_S], strict=True)
    )
    assert on_s == 1200.0
    assert instruments.floor_m2 == pytest.approx(FLOOR_M2)
    # Its 10 kW for 1200 s: 12 MJ over 76.8 m².
    assert instruments.heat_given_j(0.0, END_S) == pytest.approx(HEATER_W * on_s)
    assert values["heat-given", None] == pytest.approx(HEATER_W * on_s / 1e6 / FLOOR_M2)
    assert values["heat-given", None] == pytest.approx(0.15625)
    # 1200 s of 1800 is 16 h a day; three switches in 1/48 of a day, 144.
    assert values["device-level-hours", HEATER] == pytest.approx(on_s / HOUR_S / DAYS) == 16.0
    assert values["device-switches", HEATER] == pytest.approx(len(heater[1:]) / DAYS) == 144.0
    for idle in ("fan", "dehumidifier"):
        assert instruments.equipment[idle] == instruments.equipment[idle][:1]
        assert values["device-level-hours", idle] == values["device-switches", idle] == 0.0
    # Its three revisions, each carried out; no decision skipped.
    assert [outcome.status for outcome in record.outcomes] == [OutcomeStatus.EXECUTED] * 3
    for status in OutcomeStatus:
        expected = 3.0 if status == OutcomeStatus.EXECUTED else 0.0
        assert values["actions-by-status", status.value] == expected
    assert values["decisions-skipped", None] == 0.0
    took = sorted(decision.took_s for decision in record.trace)
    assert len(took) == 7
    assert values["decision-time-median", None] == took[3]
    assert values["decision-time-largest", None] == took[-1]
    # Half an hour harvests nothing.
    assert instruments.harvest == ()
    assert values["harvest", None] == 0.0
    # What only a benchmark gives: its goals and its prices.
    for constrained in (
        "temperature-outside-band-by-day",
        "hours-temperature-outside-band-by-night",
        "humidity-above-limit",
    ):
        value = values[constrained, None]
        goal = packaged_measure(constrained, 1).goal
        assert isinstance(value, NotComparable) and repr(goal) in value.not_comparable
    priced = values["priced-score", None]
    assert isinstance(priced, NotComparable) and "prices" in priced.not_comparable


def test_an_action_at_the_episodes_end_is_counted_and_switches_nothing(results: Path) -> None:
    """At the band above it, the rule keeps the heater on from the start
    and turns it off at the episode's end: two actions carried out, the
    heater on all the window, and no switch within it."""
    values = _values(_scores(results, 1))

    assert values["actions-by-status", OutcomeStatus.EXECUTED.value] == 2.0
    assert values["device-level-hours", HEATER] == 24.0
    assert values["device-switches", HEATER] == 0.0
    assert values["heat-given", None] == pytest.approx(HEATER_W * END_S / 1e6 / FLOOR_M2)


def test_scoring_twice_gives_the_same_scores(
    simulator: Simulator, results: Path, tmp_path: Path
) -> None:
    """Scored again from their records, each replaying to its digest, the
    episodes' scores are those the runner wrote, byte for byte, and again."""
    scored = _copied(results, tmp_path)
    shutil.rmtree(scored / "scores")
    said: list[str] = []

    for _ in range(2):
        with pytest.MonkeyPatch.context() as patch:
            patch.syspath_prepend(str(EXAMPLES))
            assert score_experiment(simulator, scored, said=said.append) == ()
        for number in range(2):
            written = (results / "scores" / f"{number}.json").read_bytes()
            assert (scored / "scores" / f"{number}.json").read_bytes() == written
    assert said[:2] == [
        f"episode {number}: scored, the same digest {digest}"
        for number, digest in enumerate(GUIDES_DIGESTS)
    ]


def test_a_record_with_its_settings_changed_is_not_scored_and_says_why(
    simulator: Simulator, results: Path, tmp_path: Path
) -> None:
    """With the second band's settings and their digest, the first record's
    episode replays to the second's digest: it is not scored, it says so,
    and its scores are left as they were; the other record is scored."""
    scored = _copied(results, tmp_path)
    path = scored / "episodes" / "0.json"
    written = json.loads(path.read_text())
    made = written["policy"]["made"]
    made["entry"]["settings"] = SECOND_BAND
    made["settings_sha256"] = settings_sha256(SECOND_BAND)
    path.write_text(json.dumps(written))
    said: list[str] = []

    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(EXAMPLES))
        assert score_experiment(simulator, scored, said=said.append) == (0,)
    first, second = said
    assert first.startswith(
        f"episode 0: not scored: it replays to another digest: the record's {GUIDES_DIGESTS[0]}"
    )
    assert f", again {GUIDES_DIGESTS[1]}" in first
    assert second == f"episode 1: scored, the same digest {GUIDES_DIGESTS[1]}"
    assert (scored / "scores" / "0.json").read_bytes() == (
        results / "scores" / "0.json"
    ).read_bytes()


def test_the_score_command_says_why_a_record_is_not_scored(
    results: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A record whose settings were changed by hand is not one: their digest
    is not that of its settings. A folder of no records is refused."""
    scored = _copied(results, tmp_path)
    (scored / "episodes" / "1.json").unlink()
    path = scored / "episodes" / "0.json"
    written = json.loads(path.read_text())
    written["policy"]["made"]["entry"]["settings"]["on_below_c"] = 16.0
    path.write_text(json.dumps(written))

    assert main(["score", str(scored)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "episode 0: not scored: policy.made: Value error, a policy's settings digest"
        " is not that of its settings"
    ]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["score", str(empty)]) == 1
    assert capsys.readouterr().err == f"refused: {empty} holds no episode's record to score\n"


class _Keeps:
    identity: Final = PolicyIdentity(name="keeps", version="1")
    decide_every_s: Final = HOUR_S

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None: ...

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        return Keep()

    def stop(self) -> None: ...


def test_the_harvest_of_a_crop_grown_by_area_is_not_comparable() -> None:
    """The instrument counts a harvest from its events, plant by plant: a
    crop grown by area has none, so its harvest is not counted as none."""
    keeps = Principal(kind=PrincipalKind.POLICY, id="keeps")
    with simulator_of(cut("tomgro_house", days=1)) as by_area:
        episode = Episode(
            scenario_id="tomgro_house", policy=_Keeps(), principal=keeps, end_s=HOUR_S
        )
        carried = carry_out_episode(by_area, episode)
        scores = score_episode(
            by_area, carried.record, carried.run, measures=[packaged_measure("harvest", 1)]
        )

    assert [(scored.name, scored.value) for scored in scores.measures] == [
        ("harvest", HARVEST_NOT_COUNTED)
    ]
