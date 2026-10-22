"""The scenarios a simulator knows (AUDIT.15, decision 0048): those packaged
with it, read from their manifests once, and those registered while it runs.

A scenario is found by its identifier, its greenhouse's, with what tells
one version of it from another: a packaged scenario's manifest digest, a
registered one's digest of its configuration. The packaged catalogue never
changes. A simulator's catalogue begins with it and adds what is registered
with that simulator: never in place of a packaged scenario, and never a
different scenario under an identifier already registered, since the runs a
simulator keeps know a scenario by its identifier alone.
"""

import json
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final, Protocol

from greenhouse_sim.digests import short_digest
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT, layout_names
from greenhouse_sim.scenarios.manifest_files import (
    DIGEST_LENGTH,
    load_manifest,
    manifest_digest,
    manifest_ids,
    opening_day,
)

# What a registered scenario may be called: as a manifest's file is, since
# its identifier is part of every address and run id that names it.
SCENARIO_ID: Final = re.compile(r"[a-z0-9_]+")


class ScenarioRefused(ValueError):
    """A scenario a catalogue will not register."""


@dataclass(frozen=True)
class CatalogueEntry:
    """A scenario as a catalogue knows it."""

    config: ScenarioConfig
    # What tells this version of the scenario from another: its manifest's
    # digest if it is packaged, its configuration's if it was registered.
    version: str
    # Where a viewer opens its run, kept as a checkpoint: packaged ones only.
    opening_day: int | None
    # Its layouts' names, its default first: a registered scenario has only
    # the one its configuration holds.
    layouts: tuple[str, ...]
    packaged: bool

    @property
    def scenario_id(self) -> str:
        return self.config.greenhouse_id


class Scenarios(Protocol):
    """Where a scenario is looked up: the packaged catalogue, or a
    simulator's."""

    def entry(self, scenario_id: str) -> CatalogueEntry | None:
        """The scenario known by this identifier, or None."""
        ...

    def ids(self) -> list[str]:
        """Every scenario's identifier: the packaged ones first, in their
        order, then those registered, as they were."""
        ...


def config_digest(config: ScenarioConfig) -> str:
    """What tells one configuration from another, however it is written."""
    canonical = json.dumps(
        config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return short_digest(canonical, DIGEST_LENGTH)


class PackagedScenarios:
    """The scenarios packaged with the simulator, which never change."""

    def __init__(self, entries: Sequence[CatalogueEntry]) -> None:
        self._entries: Mapping[str, CatalogueEntry] = MappingProxyType(
            {entry.scenario_id: entry for entry in entries}
        )
        self.configs: Mapping[str, ScenarioConfig] = MappingProxyType(
            {scenario_id: entry.config for scenario_id, entry in self._entries.items()}
        )

    @classmethod
    def read(cls) -> PackagedScenarios:
        """Every packaged scenario, read from its manifest and checked, the
        reference greenhouse first, then the others by identifier."""
        return cls(
            [
                CatalogueEntry(
                    config=load_manifest(scenario_id),
                    version=manifest_digest(scenario_id),
                    opening_day=opening_day(scenario_id),
                    layouts=tuple(layout_names(scenario_id)),
                    packaged=True,
                )
                for scenario_id in manifest_ids()
            ]
        )

    def entry(self, scenario_id: str) -> CatalogueEntry | None:
        return self._entries.get(scenario_id)

    def ids(self) -> list[str]:
        return list(self._entries)

    def with_config(self, config: ScenarioConfig) -> PackagedScenarios:
        """The same scenarios, one of them configured otherwise, as a test
        asks: versioned by its configuration, since its manifest no longer
        says what it is."""
        found = self.entry(config.greenhouse_id)
        if found is None:
            raise KeyError(f"no packaged scenario {config.greenhouse_id!r}")
        changed = replace(found, config=config, version=config_digest(config))
        return PackagedScenarios(
            [changed if entry is found else entry for entry in self._entries.values()]
        )


# The packaged scenarios, read once, as the simulator is imported.
PACKAGED: Final = PackagedScenarios.read()


class Catalogue:
    """A simulator's scenarios: the packaged ones, and those registered with
    it while it runs."""

    def __init__(self, packaged: PackagedScenarios = PACKAGED) -> None:
        self._packaged = packaged
        self._registered: dict[str, CatalogueEntry] = {}
        self._lock = threading.Lock()

    def entry(self, scenario_id: str) -> CatalogueEntry | None:
        packaged = self._packaged.entry(scenario_id)
        if packaged is not None:
            return packaged
        with self._lock:
            return self._registered.get(scenario_id)

    def ids(self) -> list[str]:
        with self._lock:
            registered = list(self._registered)
        return self._packaged.ids() + registered

    def register(self, config: ScenarioConfig) -> CatalogueEntry:
        """Know `config` as a scenario of this simulator's, by its
        greenhouse's identifier, and answer it as it is known. The same
        scenario registered again is the one already known."""
        scenario_id = config.greenhouse_id
        if not SCENARIO_ID.fullmatch(scenario_id):
            raise ScenarioRefused(
                f"a scenario is named by lowercase letters, digits and _, not {scenario_id!r}"
            )
        if self._packaged.entry(scenario_id) is not None:
            raise ScenarioRefused(f"{scenario_id!r} is a packaged scenario")
        registering = CatalogueEntry(
            config=config,
            version=config_digest(config),
            opening_day=None,
            layouts=(DEFAULT_LAYOUT,),
            packaged=False,
        )
        with self._lock:
            known = self._registered.setdefault(scenario_id, registering)
        if known.version != registering.version:
            raise ScenarioRefused(
                f"{scenario_id!r} is registered as another scenario: register a changed "
                "one under an identifier of its own"
            )
        return known
