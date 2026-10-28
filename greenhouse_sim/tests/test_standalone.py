"""The simulator runs with nothing else around it: no database, no server and
no UI.

Deliberately narrow and without fixtures, so the day that stops being true
it fails rather than quietly passes through a fixture.
"""

import pathlib
import subprocess
import sys
import textwrap


def test_a_run_loads_no_database_web_framework_or_api() -> None:
    """The simulator runs standalone, checked at runtime.

    The dependency test proves no simulator source file imports anything
    undeclared. This proves the consequence a standalone user experiences:
    working out a scenario's run and reading its observations never loads a
    database layer, a web framework, an HTTP server or the simulator's own
    local API. Run in a subprocess so modules imported by other tests do not
    count.
    """
    program = textwrap.dedent(
        """
        import sys

        from greenhouse_sim.services import sensors
        from greenhouse_sim.services.runs import RunRequest
        from greenhouse_sim.services.simulator import Simulator
        from greenhouse_sim.units import HOUR_S

        with Simulator() as simulator:
            log = sensors.observations(
                simulator, RunRequest("climate_box"), HOUR_S, from_s=0.0
            )
        assert log.observations

        leaked = sorted(
            name
            for name in sys.modules
            if name.split(".")[0] in {"sqlalchemy", "fastapi", "starlette"}
            or name == "http.server"
            or name.startswith("greenhouse_sim.api")
        )
        print(",".join(leaked))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=pathlib.Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"simulator loaded: {result.stdout!r}"
