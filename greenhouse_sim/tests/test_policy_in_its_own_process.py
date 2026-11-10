"""P15's final QA scenario (P15.7, decision 0061): a policy in a process of
its own, given only the address of a policy's port and its token, steers a
heater over the network; and the same policy, stepped by the experiment runner
in the process, steers it alike.

The tests hold the boundary between the processes, so they steer half an hour
of the climate box cut short (`policy_port_on_a_short_run`), its air quick to
work out and its heater, on no thermostat, turned on and off by the policy
alone. `GREENHOUSE_QA_HOURS` runs the QA of record instead, on the reference
greenhouse's own run, served by `python -m greenhouse_sim.api.policy_server`:
it steered a whole day (`GREENHOUSE_QA_HOURS=24`, about 25 minutes of wall
time), and a slow test runs it for a short stretch.

The port's server and the policy are real processes. The server plays the
run on the wall clock, since nothing on the port moves a held run's clock.
The runs of the two are not equal, and the tests hold what must agree:
the policy's identity as a principal, what it was refused and what it was
given, and the shape of what the heater did.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http import HTTPStatus
from itertools import pairwise
from pathlib import Path
from types import ModuleType
from typing import Any, Final
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from greenhouse_protocol.actions import SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.contracts.policy_client import HttpPolicyPort, PortRefused
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import PrincipalKind

from greenhouse_sim.experiment import Episode, EpisodeSummary, run_episode
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from policy_port_on_a_short_run import CUT
from policy_port_on_a_short_run import SCENARIO as CUT_SCENARIO
from short_runs import simulator_of

EXAMPLES: Final = Path(__file__).resolve().parents[2] / "examples"
# How much of the run's clock the policy steers, if not half an hour of the
# cut run: on the QA of record's scenario, as its server serves it.
HOURS_VARIABLE: Final = "GREENHOUSE_QA_HOURS"
OF_RECORD: Final = os.environ.get(HOURS_VARIABLE)
HOURS: Final = 0.5 if OF_RECORD is None else float(OF_RECORD)
END_S: Final = HOURS * 3600.0
REFERENCE_SCENARIO: Final = "reference_greenhouse"
# How much of it the slow test steers.
REFERENCE_HOURS: Final = 1.0
SCENARIO: Final = CUT_SCENARIO if OF_RECORD is None else REFERENCE_SCENARIO
SERVER: Final = (
    (str(Path(__file__).parent / "policy_port_on_a_short_run.py"),)
    if OF_RECORD is None
    else ("-m", "greenhouse_sim.api.policy_server")
)
# A simulated day on the server's wall clock, in seconds: the cut run's, and
# the slow test's, are slow enough that the policy's last decision has more
# than a second and a half of wall clock to fall in (`LAST_DECISION_STEPS`).
# The QA of record's is 20 s, unless `GREENHOUSE_QA_SECONDS_PER_DAY` says otherwise.
SECONDS_PER_DAY_VARIABLE: Final = "GREENHOUSE_QA_SECONDS_PER_DAY"
UNHURRIED_DAY_S: Final = 120.0
SECONDS_PER_DAY: Final = (
    UNHURRIED_DAY_S if OF_RECORD is None else float(os.environ.get(SECONDS_PER_DAY_VARIABLE, "20"))
)
# How long the server may take to say where it is, and the policy to finish.
SERVER_WAIT_S: Final = 180.0
POLICY_WAIT_S: Final = 1800.0
# How many steps before the end the policy's last decision may fall.
LAST_DECISION_STEPS: Final = 4
# How long the two examples' rule is run for: over and under both its
# thresholds, its heater on and off.
SAME_RULE_END_S: Final = 1800.0
# Set to a folder to keep what the two runs gave, as JSON.
RECORD_VARIABLE: Final = "GREENHOUSE_QA_RECORD"


def _example(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"example_{name[:2]}", EXAMPLES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REMOTE = _example("05_policy_in_its_own_process")
IN_PROCESS = _example("03_close_the_loop")


def _simulator(authorisation: AuthorisationConfig) -> Simulator:
    """A simulator of the run the policy steers, in the test's process."""
    if OF_RECORD is None:
        return simulator_of(CUT, authorisation=authorisation)
    return Simulator(authorisation=authorisation)


def _clean_environment(**extra: str) -> dict[str, str]:
    """The environment a child runs in: this one without the git hooks' or
    the running pytest's."""
    return {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PYTEST_"))} | extra


@dataclass(frozen=True)
class Served:
    """The port's server of the QA, and what the policy in its own process
    gave and saw."""

    url: str
    token: str
    remote: dict[str, Any]
    stdout: str


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Served]:
    folder = tmp_path_factory.mktemp("policy_port")
    made = subprocess.run(
        [
            sys.executable,
            "-m",
            "greenhouse_sim.api.policy_server",
            *("--new-credential", f"{REMOTE.POLICY.kind}:{REMOTE.POLICY.id}"),
        ],
        capture_output=True,
        text=True,
        check=True,
        env=_clean_environment(),
    ).stdout.splitlines()
    token = made[0].split(": ", 1)[1]
    credential = json.loads(made[1].split(": ", 1)[1])
    # The file keeps the token's hash and never the token.
    credentials = folder / "credentials.json"
    credentials.write_text(json.dumps({"version": 1, "credentials": [credential]}))
    assert token not in credentials.read_text()
    authorisation = folder / "authorisation.json"
    authorisation.write_text(REMOTE.AUTHORISATION.model_dump_json())
    log = (folder / "server.log").open("w")
    server = subprocess.Popen(
        [
            sys.executable,
            *SERVER,
            *("--scenario", SCENARIO, "--port", "0"),
            *("--credentials", str(credentials), "--authorisation", str(authorisation)),
            *("--seconds-per-day", str(SECONDS_PER_DAY)),
        ],
        stdout=subprocess.PIPE,
        stderr=log,
        text=True,
        env=_clean_environment(XDG_STATE_HOME=str(folder / "state")),
    )
    startup = threading.Timer(SERVER_WAIT_S, server.kill)
    startup.start()
    try:
        assert server.stdout is not None
        said = server.stdout.readline()
        startup.cancel()
        found = re.search(r"at (http://\S+?)/policy/v1", said)
        assert found is not None, (
            f"the port's server said {said!r}: {(folder / 'server.log').read_text()}"
        )
        url = found.group(1)
        record = folder / "remote.json"
        done = subprocess.run(
            [
                sys.executable,
                str(EXAMPLES / "05_policy_in_its_own_process.py"),
                *("--url", url, "--hours", str(HOURS), "--record", str(record)),
                "--repeat-first-revision",
            ],
            capture_output=True,
            text=True,
            timeout=POLICY_WAIT_S,
            env=_clean_environment(**{REMOTE.TOKEN_VARIABLE: token}),
        )
        assert done.returncode == 0, done.stderr
        remote = json.loads(record.read_text())
        _keep("remote", remote)
        yield Served(url=url, token=token, remote=remote, stdout=done.stdout)
    finally:
        startup.cancel()
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        log.close()


@pytest.fixture(scope="module")
def stepped() -> EpisodeSummary:
    """The same policy, stepped by the experiment runner in the process on
    the same scenario and its own seed."""
    with _simulator(REMOTE.AUTHORISATION) as simulator:
        summary = run_episode(
            simulator,
            Episode(
                scenario_id=SCENARIO,
                policy=REMOTE.NaiveHeating(),
                principal=REMOTE.POLICY,
                end_s=END_S,
                plan_id=REMOTE.PLAN_ID,
            ),
        )
    _keep("runner", json.loads(summary.model_dump_json()))
    return summary


def _keep(name: str, record: Any) -> None:
    folder = os.environ.get(RECORD_VARIABLE)
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        (Path(folder) / f"{name}.json").write_text(json.dumps(record, indent=2))


def _levels(outcomes: list[Any] | tuple[ActionOutcome, ...]) -> list[float]:
    """The heater's levels, in the order the policy's actions ran."""
    ran = [o if isinstance(o, ActionOutcome) else ActionOutcome.model_validate(o) for o in outcomes]
    ran.sort(key=lambda o: o.resolved_at)
    return [
        o.action.level
        for o in ran
        if isinstance(o.action, SetLevel) and not isinstance(o.action.level, str)
    ]


def _status(request: Request) -> int:
    try:
        with urlopen(request, timeout=30) as answer:
            return int(answer.status)
    except HTTPError as refused:
        return refused.code


def test_a_policy_in_its_own_process_steers_the_heater(served: Served) -> None:
    record = served.remote
    given = [d for d in record["decisions"] if d["receipt"] is not None]
    assert record["decisions"] and given
    # It decided every so often through the whole time, by the run's clock.
    # The last decision may fall a few steps short of the end: the wall clock
    # plays the run on while a loaded machine holds up a round of the policy's
    # requests (CI runs' last decisions were 1,480 s and 4,325 s short at 20 s
    # a simulated day: a second of wall clock was 4,320 s of the run there).
    assert record["decisions"][-1]["at_s"] > END_S - LAST_DECISION_STEPS * REMOTE.STEP_S
    assert all(d["receipt"]["accepted"] for d in given)
    # What it gave ran: each outcome is its own, executed, and sets the heater.
    outcomes = [ActionOutcome.model_validate(o) for o in record["outcomes"]]
    assert len(outcomes) == len(given)
    assert {o.status for o in outcomes} == {OutcomeStatus.EXECUTED}
    assert {o.principal for o in outcomes} == {REMOTE.POLICY}
    levels = _levels(outcomes)
    # The rule turns the heater on, then off, then on again: it read its
    # heater's warmth back from a sensor, so what it gave reached the air.
    assert len(levels) >= 2
    assert levels[:3] == [1.0, 0.0, 1.0][: len(levels)]
    assert set(levels) <= {0.0, 1.0}
    # The plan is the policy's own: the port gives it, and the operator's
    # authorisation grants a policy nothing, so only its grants allowed it.
    plan = HttpPolicyPort(served.url, served.token).plan(REMOTE.PLAN_ID)
    assert plan is not None
    assert plan.owner == REMOTE.POLICY and plan.owner.kind == PrincipalKind.POLICY
    assert plan.plan.revision == len(given)


def test_an_unknown_token_and_the_local_apis_routes_are_refused(served: Served) -> None:
    with pytest.raises(PortRefused) as unknown:
        HttpPolicyPort(served.url, "not-a-token-the-server-holds").run()
    assert unknown.value.status == HTTPStatus.UNAUTHORIZED
    with pytest.raises(PortRefused) as none:
        HttpPolicyPort(served.url, "").context()
    assert none.value.status == HTTPStatus.UNAUTHORIZED
    # Even with the policy's own token, no route of the local API is served.
    bearer = {"Authorization": f"Bearer {served.token}"}
    for method, path in (
        ("GET", "/api/scenarios"),
        ("POST", f"/api/scenarios/{SCENARIO}/runs"),
        ("GET", f"/api/scenarios/{SCENARIO}/climate/truth"),
    ):
        request = Request(
            served.url + path,
            method=method,
            headers=bearer,
            data=b"" if method == "POST" else None,
        )
        assert _status(request) == HTTPStatus.NOT_FOUND, (method, path)


def test_a_revision_given_twice_is_refused_as_stale_and_the_next_comes_from_the_plan_in_force(
    served: Served,
) -> None:
    repeated = served.remote["repeated"]
    assert repeated is not None
    assert repeated["refused_again"]
    assert not repeated["receipt"]["accepted"]
    assert repeated["receipt"]["errors"]
    # The plan in force is the revision given, so the policy counted on from it.
    assert repeated["in_force"] == repeated["revision"]
    given = [d["receipt"] for d in served.remote["decisions"] if d["receipt"] is not None]
    assert [r["revision"] for r in given] == list(range(1, len(given) + 1))


def test_the_same_policy_through_the_runner_steers_the_heater_alike(
    served: Served, stepped: EpisodeSummary
) -> None:
    remote_levels = _levels(served.remote["outcomes"])
    runner_levels = _levels(stepped.outcomes)
    assert stepped.principal == REMOTE.POLICY
    assert {o.status for o in stepped.outcomes} == {OutcomeStatus.EXECUTED}
    assert all(g.receipt.accepted for g in stepped.given)
    # Both turn the heater on first and alternate; they may differ in how
    # often, since the wall clock moves the policy's decisions and with them
    # the air its sensors read.
    for levels in (remote_levels, runner_levels):
        assert levels and levels[0] == 1.0
        assert all(a != b for a, b in pairwise(levels))
    assert stepped.decisions == int(END_S // REMOTE.STEP_S) + 1


def test_examples_03_and_05_hold_the_same_rule() -> None:
    # Example 05's policy is example 03's, kept by hand in a file that
    # imports the protocol alone: the two give the same run the same digest.
    def digest(example: ModuleType) -> str:
        with simulator_of(CUT, authorisation=example.AUTHORISATION) as simulator:
            return run_episode(
                simulator,
                Episode(
                    scenario_id=IN_PROCESS.SCENARIO,
                    policy=example.NaiveHeating(),
                    principal=example.POLICY,
                    end_s=SAME_RULE_END_S,
                ),
            ).digest

    assert digest(REMOTE) == digest(IN_PROCESS)


@pytest.mark.slow
@pytest.mark.skipif(OF_RECORD is not None, reason="this run is on the reference greenhouse")
def test_the_same_holds_on_the_reference_greenhouses_own_run(tmp_path: Path) -> None:
    """Every test above once more, in a pytest of its own, in the QA of record's
    mode for a short stretch: the server is `python -m greenhouse_sim.api.policy_server`
    itself, and a thermostat runs the heater the policy steers. The waits for
    that pytest's server and policy bound how long it takes."""
    record = tmp_path / "record"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            __file__,
            # Not slow: never this test again, whatever its environment says.
            *("-q", "-m", "not slow"),
            *("-p", "no:cacheprovider", "--basetemp", str(tmp_path / "pytest")),
        ],
        capture_output=True,
        text=True,
        env=_clean_environment(
            **{
                HOURS_VARIABLE: str(REFERENCE_HOURS),
                SECONDS_PER_DAY_VARIABLE: str(UNHURRIED_DAY_S),
                RECORD_VARIABLE: str(record),
            }
        ),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    # They ran, on that scenario, and not on the cut run or not at all.
    for kept in ("remote.json", "runner.json"):
        run_id = json.loads((record / kept).read_text())["run_id"]
        assert run_id.startswith(f"{REFERENCE_SCENARIO}-climate-")
