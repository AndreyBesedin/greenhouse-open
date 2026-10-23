"""The files the P04 final QA, `airflow-box`, draws without the API.

`web/public/scenes/qa-airflow-box.json` is the airflow QA scenario's scene,
and `web/public/fields/qa-airflow-box-cfd.json` its air as OpenFOAM solved it
(`greenhouse_sim/cfd/results/airflow_box.json`). The viewer's airflow QA page
(`/qa/airflow-box`) draws them from fixed views for its screenshot tests.
Both are written here, from `greenhouse_sim/`:

    python tests/test_airflow_qa.py --update

These tests fail if either drifts from what the simulator gives now. They
compare parsed JSON, so formatting does not count.
"""

import json
import sys
from pathlib import Path

from greenhouse_sim.services import fields, scenarios
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

ROOT = Path(__file__).resolve().parents[1]
SCENE_FILE = ROOT / "web" / "public" / "scenes" / "qa-airflow-box.json"
FIELD_FILE = ROOT / "web" / "public" / "fields" / "qa-airflow-box-cfd.json"
SCENARIO = "airflow_box"
# Scenes are compared to six decimals: platforms' maths libraries differ in
# the last bit.
DECIMALS = 6


def _rounded(value: object) -> object:
    if isinstance(value, float):
        return round(value, DECIMALS)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def _scene() -> object:
    return _rounded(scenarios.initial_scene(SCENARIO).model_dump(mode="json"))


def _field(simulator: Simulator) -> object:
    return fields.field(simulator, RunRequest(SCENARIO), "cfd").model_dump(mode="json")


def test_the_qa_scene_is_what_the_simulator_draws() -> None:
    assert json.loads(SCENE_FILE.read_text()) == _scene()


def test_the_qa_field_is_the_scenarios_kept_cfd_solution(simulator: Simulator) -> None:
    assert json.loads(FIELD_FILE.read_text()) == _field(simulator)


if __name__ == "__main__":
    with Simulator() as simulator:
        if sys.argv[1:] != ["--update"]:
            raise SystemExit("usage: python tests/test_airflow_qa.py --update")
        SCENE_FILE.write_text(json.dumps(_scene(), indent=2) + "\n")
        FIELD_FILE.parent.mkdir(parents=True, exist_ok=True)
        FIELD_FILE.write_text(json.dumps(_field(simulator)) + "\n")
        print("wrote", SCENE_FILE, FIELD_FILE)
