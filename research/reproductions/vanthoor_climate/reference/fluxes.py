"""Evaluates GreenLight 2.0.7's own heat and vapour fluxes of the air, the
cover and the sky (Vanthoor 2011, chapter 8) at the cases below, and writes
them to `fluxes.json`.

    <its venv>/bin/python -I fluxes.py <reference folder>

The venv is the one the crop's reference sets up
(`../../vanthoor_katzin/reference/setup.sh`): GreenLight's wheel, checked by
its sha256. Its definitions are read from the wheel as it installs them,
`greenhouse_vanthoor_2011_chapter_8.json`, and each flux is its own
definition evaluated, with its own functions (`sensible`, `fir`, `cond`,
`satVp`), at the case's states and inputs, every other variable at its
definition's value: the Netherlands house's parameters, with no screen
drawn and none permanent. Nothing in the repository imports GreenLight, and
nothing here is GreenLight's code but the definitions it publishes.
"""

import json
import math
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import greenlight

VERSION = "2.0.7"
DEFINITIONS = "models/katzin_2021/definition/vanthoor_2011"
CHAPTER_8 = "greenhouse_vanthoor_2011_chapter_8.json"
# The fluxes of the house air's `vanthoor` model's frame (P24.3), each per m²
# of floor, as GreenLight gives them.
FLUXES = (
    "hTopCovIn",
    "mvTopCovIn",
    "lTopCovIn",
    "hCovInCovE",
    "hCovEOut",
    "rCovESky",
    "rGlobSunCovE",
    "hecCovInCovE",
    "epsCovFir",
    "aCovPar",
    "aCovNir",
    "capCovIn",
)
# No screen drawn, and none permanent: the frame has none.
NO_SCREENS = {"uThScr": 0.0, "uShScr": 0.0, "uShScrPer": 0.0, "uBlScr": 0.0}
# Each case: the air above the canopy (the top compartment's, which the frame's
# one air is), the cover's two layers, the outside, the sky, the wind, the sun
# and the vapour pressure, and the cover's area over the floor's.
CASES: dict[str, dict[str, float]] = {
    "a cold night, the cover wet": {
        "tTop": 16.0,
        "tCovIn": 6.0,
        "tCovE": 5.2,
        "tOut": 2.0,
        "tSky": -14.0,
        "wind": 3.0,
        "iGlob": 0.0,
        "vpTop": 1500.0,
        "aCov": 1.8e4,
        "aFlr": 1.4e4,
    },
    "a sunny day, the cover dry": {
        "tTop": 24.0,
        "tCovIn": 19.5,
        "tCovE": 19.0,
        "tOut": 15.0,
        "tSky": 2.0,
        "wind": 1.5,
        "iGlob": 650.0,
        "vpTop": 1800.0,
        "aCov": 1.8e4,
        "aFlr": 1.4e4,
    },
    "the cover warmer than the air": {
        "tTop": 10.0,
        "tCovIn": 12.0,
        "tCovE": 12.5,
        "tOut": 14.0,
        "tSky": 0.0,
        "wind": 6.0,
        "iGlob": 300.0,
        "vpTop": 900.0,
        "aCov": 1.0,
        "aFlr": 1.0,
    },
    "a storm, a flat roof": {
        "tTop": 18.0,
        "tCovIn": 8.0,
        "tCovE": 7.0,
        "tOut": 5.0,
        "tSky": -20.0,
        "wind": 14.0,
        "iGlob": 50.0,
        "vpTop": 1600.0,
        "aCov": 1.0,
        "aFlr": 1.0,
    },
}


def _definitions() -> dict[str, str]:
    """Every definition of chapter 8, by its name, functions by their
    signature."""
    document = json.loads(
        resources.files(greenlight).joinpath(f"{DEFINITIONS}/{CHAPTER_8}").read_text()
    )
    found: dict[str, str] = {}

    def walk(node: Any, name: str) -> None:
        if isinstance(node, dict):
            if "definition" in node:
                found[name] = str(node["definition"])
                return
            for key, value in node.items():
                walk(value, key)

    walk(document, "")
    return found


class _Scope(dict[str, Any]):
    """The names a definition is evaluated among: the case's given, then
    each definition, evaluated as it is first asked for."""

    def __init__(self, definitions: dict[str, str], given: dict[str, float]) -> None:
        super().__init__(given)
        self._definitions = {key: value for key, value in definitions.items() if "(" not in key}
        for signature, body in definitions.items():
            if "(" in signature and not signature.startswith(("min(", "max(")):
                name, arguments = signature.split("(", 1)
                names = [part.strip() for part in arguments.rstrip(")").split(",")]
                self[name.strip()] = self._function(names, body)
        self.update({"exp": math.exp, "cos": math.cos, "pi": math.pi, "abs": abs})

    def _function(self, names: list[str], body: str) -> Any:
        def call(*values: float) -> float:
            return float(
                eval(
                    body, {"__builtins__": {}}, _Bound(self, dict(zip(names, values, strict=True)))
                )
            )

        return call

    def __missing__(self, name: str) -> Any:
        if name not in self._definitions:
            raise KeyError(name)
        value = eval(self._definitions[name], {"__builtins__": {}}, self)
        self[name] = value
        return value


class _Bound(dict[str, Any]):
    """A function's arguments, before the scope it is defined in."""

    def __init__(self, scope: _Scope, arguments: dict[str, float]) -> None:
        super().__init__(arguments)
        self._scope = scope

    def __missing__(self, name: str) -> Any:
        return self._scope[name]


def main(folder: Path) -> None:
    if greenlight.__version__ != VERSION:
        raise SystemExit(f"GreenLight {greenlight.__version__}, not {VERSION}")
    definitions = _definitions()
    cases = []
    for name, given in CASES.items():
        scope = _Scope(definitions, given | NO_SCREENS)
        cases.append(
            {
                "case": name,
                "given": given,
                "fluxes": {flux: float(scope[flux]) for flux in FLUXES},
                "satVp_tCovIn": float(scope["satVp"](given["tCovIn"])),
            }
        )
    written = {"greenlight": VERSION, "definitions": f"{DEFINITIONS}/{CHAPTER_8}", "cases": cases}
    (folder / "fluxes.json").write_text(json.dumps(written, indent=2) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
