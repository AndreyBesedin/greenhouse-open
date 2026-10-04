"""Scenarios played live for the viewer, one simulated day at a time.

A `LiveRun` steps a scenario through the engine on a background thread and
keeps the latest frame: the scene as it stands, with the simulated day and
instant. Every viewer watching the scenario shares it. The run owns no
simulation logic: it paces the engine and describes the result as a scene.

When the scenario reaches its last day it starts again from the beginning, so
a viewer left open keeps seeing it grow. Runs are deterministic, so day *d*
always looks the same; only the frame's sequence number keeps rising.
"""

import threading
from datetime import UTC, datetime, time, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.core.engine import SimulationEngine
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scene.snapshot import SceneSnapshot, scene_snapshot

# One simulated day per second by default: fast enough to watch plants grow,
# slow enough to follow.
DEFAULT_SECONDS_PER_DAY: Final = 1.0
# Simulated days start at local noon, as the examples and baselines do.
DAY_START: Final = time(12, 0)
LIVE_SIMULATION_ID: Final = "sim_live"


class LiveFrame(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    day: int
    timestamp: datetime
    snapshot: SceneSnapshot


class LiveRun:
    def __init__(self, config: ScenarioConfig, *, seconds_per_day: float) -> None:
        self._config = config
        self._seconds_per_day = seconds_per_day
        self._engine = SimulationEngine(config)
        plant_count = config.rows * config.columns
        self._plant_ids = [
            f"{config.greenhouse_id}_plant_{i:03d}" for i in range(1, plant_count + 1)
        ]
        self._start = datetime.combine(config.start_date, DAY_START, tzinfo=UTC)
        self._changed = threading.Condition()
        self._stopped = threading.Event()
        self._world = self._engine.initialize(self._plant_ids, greenhouse_id=config.greenhouse_id)
        self._frame = self._describe(sequence=0, day=0)
        self._thread = threading.Thread(target=self._play, daemon=True)

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        with self._changed:
            self._changed.notify_all()

    def latest(self) -> LiveFrame:
        with self._changed:
            return self._frame

    def frame_after(self, sequence: int | None, timeout: float) -> LiveFrame | None:
        """The latest frame once it is newer than `sequence`, or None if no new
        frame arrives within `timeout` seconds or the run stops."""
        with self._changed:
            self._changed.wait_for(
                lambda: self.stopped or sequence is None or self._frame.sequence > sequence,
                timeout,
            )
            if self.stopped or (sequence is not None and self._frame.sequence <= sequence):
                return None
            return self._frame

    def advance(self) -> LiveFrame:
        """Moves the run on by one simulated day, starting over after the last."""
        with self._changed:
            day = self._frame.day + 1
            if day > self._config.duration_days:
                day = 0
                self._world = self._engine.initialize(
                    self._plant_ids, greenhouse_id=self._config.greenhouse_id
                )
            else:
                self._world = self._engine.advance(
                    self._world,
                    day=day,
                    timestamp=self._timestamp(day),
                    simulation_id=LIVE_SIMULATION_ID,
                ).world
            self._frame = self._describe(sequence=self._frame.sequence + 1, day=day)
            self._changed.notify_all()
            return self._frame

    def _play(self) -> None:
        while not self._stopped.wait(self._seconds_per_day):
            self.advance()

    def _timestamp(self, day: int) -> datetime:
        return self._start + timedelta(days=day)

    def _describe(self, *, sequence: int, day: int) -> LiveFrame:
        return LiveFrame(
            sequence=sequence,
            day=day,
            timestamp=self._timestamp(day),
            snapshot=scene_snapshot(self._world, self._config),
        )


class LiveRuns:
    """One shared run per scenario, started when a viewer first asks for it."""

    def __init__(self, *, seconds_per_day: float = DEFAULT_SECONDS_PER_DAY) -> None:
        self._seconds_per_day = seconds_per_day
        self._runs: dict[str, LiveRun] = {}
        self._lock = threading.Lock()

    def run_for(self, config: ScenarioConfig) -> LiveRun:
        with self._lock:
            run = self._runs.get(config.greenhouse_id)
            if run is None:
                run = LiveRun(config, seconds_per_day=self._seconds_per_day)
                run.start()
                self._runs[config.greenhouse_id] = run
            return run

    def stop(self) -> None:
        with self._lock:
            for run in self._runs.values():
                run.stop()
