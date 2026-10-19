"""Versions pinned in two places, held together.

Dependabot proposes each release from one place; the other follows by hand
on its pull request, which fails here until it does and says what to move
(docs/roadmap/README.md, Dependabot).
"""

import json
import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
LOCKED = {
    package["name"]: package.get("version")
    for package in tomllib.loads((ROOT / "uv.lock").read_text())["package"]
}
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
VIEWER_LOCK = ROOT / "greenhouse_sim" / "web" / "package-lock.json"
_PLAYWRIGHT_IMAGE = re.compile(r"mcr\.microsoft\.com/playwright:v([0-9.]+)-")


def _pins(requirements: list[str]) -> dict[str, str]:
    """The exact pins among `requirements`, by name."""
    pins = {}
    for requirement in requirements:
        name, _, version = requirement.partition("==")
        if version:
            pins[name.strip()] = version.strip()
    return pins


TOOLCHAIN = _pins(PYPROJECT["dependency-groups"]["toolchain"])


def _setup_uv_inputs(workflow: str) -> list[list[str]]:
    """The lines under each step that sets uv up: its `with:` inputs."""
    lines = workflow.splitlines()
    steps = []
    for at, line in enumerate(lines):
        if "uses: astral-sh/setup-uv@" not in line:
            continue
        dash = line.index("-")
        inputs = []
        for following in lines[at + 1 :]:
            if following.strip() and len(following) - len(following.lstrip()) <= dash:
                break
            inputs.append(following.strip())
        steps.append(inputs)
    return steps


def test_every_job_installs_the_uv_the_lock_records() -> None:
    # setup-uv installs the latest uv when the lock records none.
    steps = [
        (workflow.name, inputs)
        for workflow in WORKFLOWS
        for inputs in _setup_uv_inputs(workflow.read_text())
    ]

    assert steps
    assert [name for name, inputs in steps if "version-file: uv.lock" not in inputs] == []
    assert LOCKED.get("uv") == TOOLCHAIN["uv"]


def test_uv_builds_the_root_project_itself() -> None:
    # Outside its `uv_build` range, uv would build the root project with a
    # `uv_build` from PyPI, which uv.lock does not pin.
    backend = Requirement(PYPROJECT["build-system"]["requires"][0])
    uv = TOOLCHAIN["uv"]

    assert Version(uv) in backend.specifier, (
        f"CI's uv is {uv}, outside the root project's `{backend}`: widen it in the root "
        "pyproject.toml's [build-system], then run `uv lock`."
    )


def test_the_packages_build_with_the_backend_the_toolchain_pins() -> None:
    # uv.lock pins what is installed, not what builds it: the workspace's
    # build pin is the `toolchain` group's, whose releases Dependabot
    # proposes.
    uv = PYPROJECT["tool"]["uv"]
    built_with = _pins(uv.get("build-constraint-dependencies", []))
    backends = {
        Requirement(requirement).name
        for member in uv["workspace"]["members"]
        for requirement in tomllib.loads((ROOT / member / "pyproject.toml").read_text())[
            "build-system"
        ]["requires"]
    }

    assert backends
    for backend in sorted(backends):
        assert backend in TOOLCHAIN, f"{backend} builds the packages: pin it in `toolchain`."
        assert built_with.get(backend) == TOOLCHAIN[backend], (
            f"The packages build with {backend} {built_with.get(backend)}, `toolchain` pins "
            f"{TOOLCHAIN[backend]}: move the root pyproject.toml's "
            f'build-constraint-dependencies to "{backend}=={TOOLCHAIN[backend]}", then run '
            "`uv lock`."
        )


def test_the_visual_checks_run_in_the_image_of_the_viewers_playwright() -> None:
    # The image holds its own version's browsers; another @playwright/test
    # finds none.
    images = set(_PLAYWRIGHT_IMAGE.findall((ROOT / ".github" / "workflows" / "ci.yml").read_text()))
    lock = json.loads(VIEWER_LOCK.read_text())
    playwright = lock["packages"]["node_modules/@playwright/test"]["version"]

    assert images, "ci.yml names no Playwright image"
    assert images == {playwright}, (
        f"The viewer has @playwright/test {playwright}, the visual checks' image "
        f"{', '.join(sorted(images))}: move ci.yml's image to "
        f"mcr.microsoft.com/playwright:v{playwright}-noble-amd64."
    )
