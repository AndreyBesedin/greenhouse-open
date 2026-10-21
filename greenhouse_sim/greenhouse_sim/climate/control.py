"""A greenhouse's climate controller, as data (P11.1): the loops that run its
heater, vents, fans and dehumidifier by its house's air, each with its
targets and its band, its vents in stages, as a climate computer runs them
(`docs/roadmap/p11-climate-setpoints.md`).

Each loop reads one quantity of the air and switches its devices in steps,
with hysteresis: every edge it switches at is a value of the air, with a
band of positive width between switching on and switching off, so that the
air must cross the band between two switches of one loop and time always
moves on. A loop that depends on another reads that loop's state, never
the air at the other's edge. Heating and venting keep a dead band between
them, so the house never heats and vents for temperature at once.

The rules are exploratory heuristics: they follow the usual structure of a
climate computer's heating and venting, but no source has yet been checked
against each one's specifics. The heating loop is decision 0042's
thermostat (`climate.thermostat`), which a run follows today; the house
decides the other loops from P11.2, and until then a scenario's control
holds its heating loop alone (`scenarios.config`).
"""

from typing import Annotated, Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

from greenhouse_sim.climate.thermostat import MINUTE_S, Thermostat, TimeOfDay
from greenhouse_sim.units import HOUR_S

# Where a controller's day and night start, by default: decision 0042's.
DAY_FROM_S: Final = 7 * HOUR_S
NIGHT_FROM_S: Final = 19 * HOUR_S

# How far a vent stands open at a stage, more than closed and at most open.
type StageLevel = Annotated[float, Field(gt=0.0, le=1.0)]
# A relative humidity, in percent, that air can hold short of saturation.
type HumidityPct = Annotated[float, Field(gt=0.0, lt=100.0)]


class HeatingLoop(BaseModel):
    """Heat the house's air with the heater `actuator_id` to `day_c` by day
    and `night_c` by night: on below the setpoint by half `band_c`, off above
    it by as much (decision 0042's thermostat)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actuator_id: str
    day_c: float
    night_c: float
    band_c: PositiveFloat = 1.0

    def off_above_c(self, setpoint_c: float) -> float:
        """The air's temperature above which it switches its heater off."""
        return setpoint_c + self.band_c / 2


class VentStage(BaseModel):
    """A stage of the vents: open to `level` once the air passes the venting
    setpoint by `above_c`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    above_c: NonNegativeFloat
    level: StageLevel


class VentingLoop(BaseModel):
    """Vent the house's air through the vents `vents`, to `day_c` by day and
    `night_c` by night, in `stages`: each opens when the air passes the
    setpoint plus its `above_c`, and closes when the air falls back below
    that by `band_c`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vents: list[str] = Field(min_length=1)
    day_c: float
    night_c: float
    band_c: PositiveFloat = 1.0
    stages: list[VentStage] = Field(min_length=1)

    @model_validator(mode="after")
    def _its_stages_in_order(self) -> Self:
        if len(set(self.vents)) < len(self.vents):
            raise ValueError("a venting loop names each of its vents once")
        for lower, higher in zip(self.stages, self.stages[1:], strict=False):
            if not (lower.above_c < higher.above_c and lower.level < higher.level):
                raise ValueError(
                    "a venting loop's stages open further, each at a higher temperature than "
                    "the one before"
                )
        return self

    def first_closes_below_c(self, setpoint_c: float) -> float:
        """The air's temperature below which its first stage closes."""
        return setpoint_c + self.stages[0].above_c - self.band_c


class CirculationLoop(BaseModel):
    """Run the fans `fans` while the vents stand open at stage `from_stage`,
    counted from 1, or beyond."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fans: list[str] = Field(min_length=1)
    from_stage: PositiveInt = 1

    @model_validator(mode="after")
    def _each_fan_once(self) -> Self:
        if len(set(self.fans)) < len(self.fans):
            raise ValueError("a circulation loop names each of its fans once")
        return self


class DehumidifyingLoop(BaseModel):
    """Dry the house's air to `target_pct` relative humidity: the
    dehumidifier `actuator_id` on above the target by half `band_pct`, off
    below it by as much. With `vents_when_drier`, the vents' first stage
    opens too, while this loop is on, the heater off, and the air outside is
    drier than the house's: its humidity ratio lower by `drier_by_g_kg`,
    until it is lower by less than that less `drier_band_g_kg`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actuator_id: str
    target_pct: HumidityPct
    band_pct: PositiveFloat = 5.0
    vents_when_drier: bool = True
    drier_by_g_kg: PositiveFloat = 1.0
    drier_band_g_kg: PositiveFloat = 0.5

    @model_validator(mode="after")
    def _its_band_within_reach(self) -> Self:
        half = self.band_pct / 2
        if not 0.0 < self.target_pct - half < self.target_pct + half < 100:
            raise ValueError("a dehumidifying loop's band lies between dry air and saturation")
        if self.drier_band_g_kg >= self.drier_by_g_kg:
            raise ValueError(
                "a dehumidifying loop vents only while the air outside is drier: its band is "
                "narrower than its margin"
            )
        return self


class Control(BaseModel):
    """A greenhouse's climate controller: its loops, a day from
    `day_from_s` and a night from `night_from_s`, times of a run's day on
    the minute that every loop's targets share, and the dead band
    `dead_band_c` that keeps heating and venting apart: in each period, the
    vents' first stage closes above the temperature the heater switches off
    at by at least that much."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day_from_s: TimeOfDay = DAY_FROM_S
    night_from_s: TimeOfDay = NIGHT_FROM_S
    dead_band_c: PositiveFloat = 1.0
    heating: HeatingLoop | None = None
    venting: VentingLoop | None = None
    circulation: CirculationLoop | None = None
    dehumidifying: DehumidifyingLoop | None = None

    @model_validator(mode="after")
    def _a_day_between_two_nights(self) -> Self:
        if not self.day_from_s < self.night_from_s:
            raise ValueError("a controller's day starts before its night, in a run's day")
        if self.day_from_s % MINUTE_S or self.night_from_s % MINUTE_S:
            raise ValueError("a controller's day and night start on the minute")
        return self

    @model_validator(mode="after")
    def _a_loop_at_least(self) -> Self:
        if not self.loops():
            raise ValueError("a controller runs one loop at least")
        return self

    @model_validator(mode="after")
    def _heating_and_venting_apart(self) -> Self:
        if self.heating is None or self.venting is None:
            return self
        for period, heat_c, vent_c in (
            ("day", self.heating.day_c, self.venting.day_c),
            ("night", self.heating.night_c, self.venting.night_c),
        ):
            gap = self.venting.first_closes_below_c(vent_c) - self.heating.off_above_c(heat_c)
            if gap < self.dead_band_c:
                raise ValueError(
                    f"by {period}, the vents' first stage closes {gap:.15g} °C above where the "
                    f"heater switches off, within the dead band of {self.dead_band_c:.15g} °C"
                )
        return self

    @model_validator(mode="after")
    def _what_a_loop_reads_is_run(self) -> Self:
        if self.circulation is not None:
            if self.venting is None:
                raise ValueError("a circulation loop follows the vents: a venting loop runs them")
            if self.circulation.from_stage > len(self.venting.stages):
                raise ValueError(
                    f"a circulation loop follows the vents from stage "
                    f"{self.circulation.from_stage}, and they have {len(self.venting.stages)}"
                )
        if (
            self.dehumidifying is not None
            and self.dehumidifying.vents_when_drier
            and self.venting is None
        ):
            raise ValueError(
                "a dehumidifying loop that vents opens the vents' first stage: a venting loop "
                "runs them"
            )
        return self

    def loops(self) -> list[str]:
        """The names of the loops it runs, in the order a period's targets
        are given."""
        loops = {
            "heating": self.heating,
            "venting": self.venting,
            "circulation": self.circulation,
            "dehumidifying": self.dehumidifying,
        }
        return [name for name, loop in loops.items() if loop is not None]

    def runs(self) -> list[str]:
        """Every device its loops run: its heater, vents, fans and
        dehumidifier."""
        devices: list[str] = []
        if self.heating is not None:
            devices.append(self.heating.actuator_id)
        if self.venting is not None:
            devices += self.venting.vents
        if self.circulation is not None:
            devices += self.circulation.fans
        if self.dehumidifying is not None:
            devices.append(self.dehumidifying.actuator_id)
        return devices

    def thermostat(self) -> Thermostat | None:
        """Its heating loop as the thermostat a run follows, at its day's and
        night's times; none without one."""
        if self.heating is None:
            return None
        return Thermostat(
            actuator_id=self.heating.actuator_id,
            day_c=self.heating.day_c,
            night_c=self.heating.night_c,
            day_from_s=self.day_from_s,
            night_from_s=self.night_from_s,
            band_c=self.heating.band_c,
        )
