"""The plant lab holds every plant of a run to the structure's rules, and to
what a plant may do from one day to the next, and says what is wrong."""

from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.tomato.organ.development import DevelopmentParams
from greenhouse_sim.biology.tomato.organ.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.services import plants
from greenhouse_sim.services.plants import LabAction, LabChecks, LabRun


@pytest.mark.parametrize(
    "run",
    [
        LabRun(day=0),
        LabRun(day=45, seed=7),
        LabRun(day=90, environment="cool_dim", versus="warm_bright"),
        LabRun(
            day=40,
            actions=(
                LabAction(day=30, plant_id="p01", kind="remove_leaf", target="p01_n01_leaf"),
                LabAction(day=31, plant_id="p01", kind="lower_stem", target="1"),
                LabAction(day=31, plant_id="p02", kind="lower_stem", target="1"),
            ),
        ),
    ],
)
def test_every_plant_of_a_run_keeps_every_rule(run: LabRun) -> None:
    checks = plants.checks(run)

    assert checks.day == run.day
    assert sorted(checks.problems) == plants.plant_ids()
    assert all(problems == [] for problems in checks.problems.values())


def test_a_plant_that_goes_wrong_overnight_is_named_with_what_went_wrong(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def back_in_time(plant: Plant, _: LocalEnvironment, __: DevelopmentParams) -> Plant:
        return plant.model_copy(update={"thermal_time": 0.0})

    monkeypatch.setattr(plants, "live_day", back_in_time)
    problems = plants.checks(LabRun(day=1)).problems["p05"]

    assert "the plant's thermal time went back" in problems
    assert "p05_n02 appeared after the plant's thermal time" in problems


def test_the_lab_answers_with_its_checks_and_refuses_a_run_it_cannot_make() -> None:
    answer = respond("GET", "/api/plants/checks?day=3&seed=4")
    refused = respond("GET", "/api/plants/checks?environment=tropical")

    assert answer.status == HTTPStatus.OK
    assert LabChecks.model_validate(answer.body) == plants.checks(LabRun(day=3, seed=4))
    assert refused.status == HTTPStatus.BAD_REQUEST
