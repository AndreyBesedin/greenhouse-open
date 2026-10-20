"""A run replayed (P09.5): its state probed at each day's end and digested,
the same on every replay, the same before a branch's first change and not
after, and the reference run's first days matching the digests kept here.

The kept digests are the reference run's as the simulator replays it today.
When a deliberate change moves them, rewrite them from `greenhouse_sim/`:

    python tests/test_replay.py --update

and say why in the commit message. They are kept for the manifest they
were made with: a change to the reference scenario's manifest asks for
them to be written again.
"""

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.manifest_files import manifest_digest
from greenhouse_sim.services.fields import house_air_at
from greenhouse_sim.services.replay import ROUNDED_DECIMALS, DayProbe, _rounded, day_probes

FIXTURE: Final = Path(__file__).resolve().parent / "fixtures" / "reference_replay.json"
SCENARIO: Final = "reference_greenhouse"
# How many of the reference run's first days are kept.
KEPT_DAYS: Final = 3
# The reference run's heater, off an hour into its second day: a branch.
BRANCH: Final = [(DAY_S + 3600.0, "heater", 0.0)]


def test_the_reference_runs_first_days_replay_to_the_digests_kept() -> None:
    kept = json.loads(FIXTURE.read_text())

    assert kept["manifest"] == manifest_digest(SCENARIO), (
        "the reference scenario's manifest has changed: "
        "write its replay again with `python tests/test_replay.py --update`"
    )
    replayed = day_probes(SCENARIO, KEPT_DAYS)
    assert [probe.model_dump() for probe in replayed] == kept["days"]


def test_a_replay_gives_the_same_digests_and_a_branch_the_same_before_its_change() -> None:
    first = day_probes(SCENARIO, 2)
    again = day_probes(SCENARIO, 2)
    branch = day_probes(SCENARIO, 2, commands=BRANCH)

    assert again == first
    assert branch[0] == first[0]
    assert branch[1].digest != first[1].digest
    # Its heater off for the small hours of its second day, before its own
    # schedule's morning heat, its crop develops less that day.
    assert branch[1].thermal_time_cd < first[1].thermal_time_cd


def test_a_replay_gives_the_same_digests_after_a_viewer_scrubbed_the_run(
    afresh: Callable[[], None],
) -> None:
    # A moment between the run's minutes, asked for first, changes nothing
    # that is worked out after it.
    fresh = day_probes(SCENARIO, 1)
    afresh()
    house_air_at(SCENARIO, time_s=DAY_S - 30.0)

    assert day_probes(SCENARIO, 1) == fresh


def test_a_probe_is_rounded_before_it_is_digested() -> None:
    assert _rounded({"a": [1.0000001234, "x", 2], "b": 0.1 + 0.2}) == {
        "a": [round(1.0000001234, ROUNDED_DECIMALS), "x", 2],
        "b": 0.3,
    }
    probe = day_probes(SCENARIO, 1)[0]
    assert isinstance(probe, DayProbe)
    assert probe.readings > 0 and probe.organs > 0


def _update() -> None:
    kept = {
        "scenario_id": SCENARIO,
        "manifest": manifest_digest(SCENARIO),
        "days": [probe.model_dump() for probe in day_probes(SCENARIO, KEPT_DAYS)],
    }
    FIXTURE.parent.mkdir(exist_ok=True)
    FIXTURE.write_text(json.dumps(kept, indent=2) + "\n")


def test_large_numbers_are_told_apart_by_their_run_not_their_machine() -> None:
    # A season's heat in joules, as macOS and Linux worked it out (#246):
    # the same to twelve significant digits, not to six decimals.
    assert _rounded(68523090804.529655) == _rounded(68523090804.52964)
    assert _rounded(68523090804.529655) != _rounded(68523090904.529655)
    assert _rounded(15.9194131234) == 15.919413


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_replay.py --update")
    _update()
    print(f"wrote {FIXTURE}")
