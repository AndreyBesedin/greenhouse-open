"""Run an experiment, check one of its records (P23.3), or score its
records again (P25.3):

    python -m greenhouse_sim.experiment run experiment.json --out results/
    python -m greenhouse_sim.experiment check results/episodes/3.json
    python -m greenhouse_sim.experiment score results/

Each takes `--authorisation FILE`, who may do what on the runs (decision
0052), by default the local operator's alone: a policy's principal that
acts needs a grant, and a check or a score needs the one its run was
given. `check` exits 1 when its digest is not the record's, or the record
cannot be read as one, saying why. `score` scores each record whose
episode replays to its digest, says of each other why it is not scored,
and exits 1 if any is not.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from greenhouse_protocol.experiment import EpisodeRecord

from greenhouse_sim.experiment.paired import (
    check_record,
    refusal,
    run_experiment,
    score_experiment,
)
from greenhouse_sim.services.errors import ServiceError
from greenhouse_sim.services.gateway import LOCAL_AUTHORISATION, authorisation_file
from greenhouse_sim.services.simulator import Simulator


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an experiment, check a record of it, or score its records again."
    )
    parser.add_argument(
        "--authorisation",
        type=Path,
        default=None,
        help="a JSON file of who may do what on the runs; by default the local operator's",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run every episode of an experiment's file")
    run.add_argument("experiment", type=Path)
    run.add_argument("--out", type=Path, required=True, help="a directory, new or empty")
    check = commands.add_parser("check", help="run a record's episode again and compare")
    check.add_argument("record", type=Path)
    score = commands.add_parser(
        "score", help="run each record's episode again and score those that replay"
    )
    score.add_argument("results", type=Path, help="an experiment's directory, as run writes it")
    args = parser.parse_args(argv)
    try:
        authorisation = (
            LOCAL_AUTHORISATION
            if args.authorisation is None
            else authorisation_file(args.authorisation)
        )
        with Simulator(authorisation=authorisation) as simulator:
            if args.command == "run":
                run_experiment(simulator, args.experiment.read_bytes(), args.out)
                return 0
            if args.command == "score":
                return 1 if score_experiment(simulator, args.results) else 0
            record = EpisodeRecord.model_validate_json(args.record.read_bytes())
            checked = check_record(simulator, record)
    except (OSError, ValueError, ServiceError) as error:
        print(f"refused: {refusal(error)}", file=sys.stderr)
        return 1
    if checked.same:
        print(f"the same digest, {checked.again}")
        return 0
    print(f"another digest: the record's {checked.recorded}, again {checked.again}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
