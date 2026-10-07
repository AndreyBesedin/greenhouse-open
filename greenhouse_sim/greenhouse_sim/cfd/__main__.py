"""Write a scenario's CFD case, and mesh it if asked.

    python -m greenhouse_sim.cfd gh_001 cases/gh_001
    python -m greenhouse_sim.cfd gh_001 cases/gh_001 --open roof_vent_1:0.5 --mesh

The case is written as the API's `/cfd/geometry` describes it, with the same
changes: `--layout`, `--envelope length:12,spans:3` and `--open`. `--mesh`
meshes it with OpenFOAM, installed or in its container, and says what it
made; the case's `Allmesh` script does the same anywhere OpenFOAM is.
"""

import argparse
from pathlib import Path

from greenhouse_sim.cfd.openfoam import MeshFailed, mesh
from greenhouse_sim.cfd.runner import OpenFoamUnavailable
from greenhouse_sim.services import cfd
from greenhouse_sim.services.errors import ServiceError
from greenhouse_sim.services.scenarios import SceneChanges


def _pairs(text: str | None) -> dict[str, float]:
    """`key:number,key:number` as numbers by key."""
    pairs: dict[str, float] = {}
    for pair in (text or "").split(","):
        if pair:
            key, _, number = pair.partition(":")
            pairs[key] = float(number)
    return pairs


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m greenhouse_sim.cfd", description=__doc__)
    parser.add_argument("scenario", help="the scenario's identifier, such as gh_001")
    parser.add_argument("directory", type=Path, help="where the case is written")
    parser.add_argument("--layout", help="another of the scenario's layouts")
    parser.add_argument("--envelope", help="the greenhouse's dimensions, as length:12,spans:3")
    parser.add_argument("--open", help="how far doors and vents stand open, as roof_vent_1:0.5")
    parser.add_argument("--mesh", action="store_true", help="mesh the case with OpenFOAM")
    args = parser.parse_args(arguments)

    try:
        changes = SceneChanges(
            envelope=_pairs(args.envelope),
            openings=_pairs(args.open),
            **({"layout": args.layout} if args.layout else {}),
        )
    except ValueError as error:
        parser.error(str(error))
    try:
        written = cfd.write_case(args.scenario, args.directory, changes)
    except ServiceError as error:
        parser.error(error.message)
    print(f"wrote {len(written)} files of {args.scenario}'s case to {args.directory}")
    if not args.mesh:
        return 0
    try:
        meshed = mesh(args.directory)
    except (OpenFoamUnavailable, MeshFailed) as error:
        print(error)
        return 1
    print(f"meshed {meshed.cells} cells")
    for patch in meshed.patches:
        print(f"  {patch.name}: {patch.faces} faces, {patch.kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
