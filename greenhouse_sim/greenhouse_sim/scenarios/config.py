from datetime import UTC, date, datetime
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt, model_validator

from greenhouse_sim.airflow.prescribed import PrescribedAirflow, UniformAirflow
from greenhouse_sim.cfd.setup import CfdSetup
from greenhouse_sim.climate.commands import DailyCommand
from greenhouse_sim.climate.control import Control
from greenhouse_sim.climate.settings import GridAir, WholeHouseAir
from greenhouse_sim.climate.thermostat import Thermostat
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import CropWork
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.scenarios.crop_parameters import (
    DEFAULT_SIMPLE_CROP,
    HELD_AT_THE_TOP,
    WALK,
    CropWalk,
    OrganCrop,
    SimpleCrop,
)
from greenhouse_sim.weather.recorded import RecordedWeather
from greenhouse_sim.weather.seasonal import SeasonalWeather
from greenhouse_sim.weather.sources import Clouded, ConstantWeather, RunWeather, Winded
from greenhouse_sim.weather.state import Percent
from greenhouse_sim.weather.synthetic import SyntheticWeather
from greenhouse_sim.world.capabilities import Capability, Dries, Heats, MovesAir
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.equipment import can
from greenhouse_sim.world.layout import Layout, inside_the_greenhouse, outside_the_greenhouse
from greenhouse_sim.world.site import DEFAULT_SITE, Bearing, Site

# A refusal names this many of the things it refuses, and counts the rest.
NAMED_IN_A_REFUSAL = 3


def _with_its_airs_kind(given: dict[str, Any]) -> dict[str, Any]:
    """A configuration whose house's air names no model, as one written
    before P14.6 does, with the grid's: what its runs were."""
    air = given.get("climate")
    if isinstance(air, dict) and "kind" not in air:
        return given | {"climate": air | {"kind": "grid"}}
    if isinstance(air, BaseModel) and not isinstance(air, GridAir | WholeHouseAir):
        return given | {"climate": {**air.model_dump(), "kind": "grid"}}
    return given


class ScenarioConfig(BaseModel):
    """The simulated world: its greenhouse, crop, dynamics and sensor noise.

    Which management policy runs against it, and with what thresholds, is
    not part of the world. That is the caller's choice about a run.
    """

    # A scenario does not change once made, as a catalogue knows it by its
    # version (decision 0048): another is made from it (`model_copy`).
    model_config = ConfigDict(frozen=True)

    greenhouse_id: str
    name: str
    description: str
    variety: str
    # The crop: rows times columns plants, standing at the layout's planting
    # positions in order.
    rows: PositiveInt
    columns: PositiveInt
    # How its runs grow the crop: by the simple daily model, through the
    # engine, or organ by organ, each day from the run's air and each plant's
    # own light (`greenhouse_sim.core.crop`); and what they do to it.
    crop_model: CropModel = CropModel.SIMPLE
    # Its crop model's parameters, of the model its rows grow: by default,
    # that model's own (`greenhouse_sim.scenarios.crop_parameters`).
    crop: Annotated[SimpleCrop | OrganCrop, Field(discriminator="kind")] = SimpleCrop()
    crop_work: CropWork = CropWork()
    # The daily walk through its crop's measurement errors.
    crop_walk: CropWalk = CropWalk()
    # The commands its runs give its equipment, doors and vents at a time of
    # day, every day, unless a run is given daily commands of its own (P09.4).
    daily: list[DailyCommand] = []
    # Its climate controller (P11): the loops that run its heater, vents,
    # fans and dehumidifier by the house's air from the start, in place of
    # daily commands to them: the parameters of the controller's model
    # `loops` (P14.6); none by default, the model `none`. Its heating loop
    # is the thermostat on its heater (P10.3); until the house decides
    # every loop (P11.2), it is the only loop a scenario may have.
    control: Control | None = None
    start_date: date
    duration_days: PositiveInt
    random_seed: NonNegativeInt
    # The greenhouse around the crop: where it stands, and the space it encloses.
    envelope: Envelope
    # What stands inside it, in its frame, including where the plants stand.
    layout: Layout = Layout()
    # How its air moves: a prescribed pattern, until a solver says otherwise.
    airflow: PrescribedAirflow = UniformAirflow()
    # How a CFD solver drives its air: by default, in through its first open
    # door or vent and out through the others.
    cfd: CfdSetup = CfdSetup()
    # How its runs work out the house's air (P14.6): the whole house alone,
    # or cell by cell beside it, the default; and what its air starts from,
    # and how it exchanges with the outside, when its equipment drives it.
    climate: Annotated[GridAir | WholeHouseAir, Field(discriminator="kind")] = GridAir()
    # Where it lies on the Earth, and the weather outside it.
    site: Site = DEFAULT_SITE
    weather: Annotated[
        ConstantWeather | SyntheticWeather | SeasonalWeather | RecordedWeather,
        Field(discriminator="kind"),
    ] = ConstantWeather()
    # A QA override of its weather's cloud cover, which dims its light as
    # such a sky would (`greenhouse_sim.weather.sources.Clouded`); none by
    # default.
    cloud_cover_pct: Percent | None = None
    # A QA override of its weather's wind direction, the compass bearing it
    # blows from (`greenhouse_sim.weather.sources.Winded`); none by default.
    wind_from_deg: Bearing | None = None

    @model_validator(mode="before")
    @classmethod
    def _its_crop_takes_its_models_parameters(cls, given: Any) -> Any:
        """A configuration given its crop model, not its parameters, takes
        that model's own; and given the settings it held at its top until
        P14.3, as one written before may be, takes them in their sections:
        the walk's in its crop walk, the simple crop's in its crop if it is
        the simple crop, and not at all if it is another, since they were
        the engine's for the simple crop in its place; and given its house's
        air with no model, as before P14.6, takes the grid's."""
        if not isinstance(given, dict):
            return given
        given = _with_its_airs_kind(given)
        grown = given.get("crop_model", CropModel.SIMPLE)
        kinds = {"crop": str(grown), "crop_walk": WALK}
        sections = dict(given)
        for section, names in HELD_AT_THE_TOP.items():
            held = {name: sections.pop(name) for name in names if name in sections}
            if held and section in sections:
                raise ValueError(f"its {section} holds {', '.join(held)}, not beside it")
            if section == "crop" and grown != CropModel.SIMPLE:
                held = {}
            if held:
                sections[section] = {"kind": kinds[section], **held}
        if "crop" not in sections and grown in tuple(CropModel):
            sections["crop"] = {"kind": str(grown)}
        return sections

    @model_validator(mode="after")
    def _its_crop_is_the_one_its_rows_grow(self) -> Self:
        if self.crop.kind != self.crop_model:
            raise ValueError(
                f"its crop's parameters are the {self.crop.kind} crop's, but it grows the "
                f"{self.crop_model} crop"
            )
        return self

    @property
    def simple_crop(self) -> SimpleCrop:
        """The simple crop's settings, by which the engine's day grows its
        crop: its crop's, or the simple crop's own if its crop is of another
        model."""
        return self.crop if isinstance(self.crop, SimpleCrop) else DEFAULT_SIMPLE_CROP

    def run_start(self) -> datetime:
        """The instant its runs start: its start date's midnight at its site."""
        return self.site.midnight(self.start_date).astimezone(UTC)

    def run_length_s(self) -> float:
        """How long its runs last, in seconds: to its last day's end
        (`greenhouse_sim.core.clock`)."""
        return self.duration_days * DAY_S

    def run_weather(self) -> RunWeather:
        """Its weather on a run's clock, its clouds and its wind's direction
        as overridden, if they are."""
        start = self.run_start()
        source = self.weather.source(self.site, self.random_seed, start)
        if self.cloud_cover_pct is not None:
            source = Clouded(source, self.cloud_cover_pct)
        if self.wind_from_deg is not None:
            source = Winded(source, self.wind_from_deg)
        return RunWeather(source, start)

    @model_validator(mode="after")
    def _the_layout_fits_in_the_greenhouse(self) -> Self:
        outside = outside_the_greenhouse(self.layout, self.envelope)
        if outside:
            named = ", ".join(outside[:NAMED_IN_A_REFUSAL])
            more = len(outside) - NAMED_IN_A_REFUSAL
            raise ValueError(
                f"outside the greenhouse: {named}" + (f" and {more} more" if more > 0 else "")
            )
        return self

    @model_validator(mode="after")
    def _the_weather_station_stands_outside(self) -> Self:
        inside = inside_the_greenhouse(self.layout, self.envelope)
        if inside:
            raise ValueError(f"a weather station stands outside the house, not {inside[0]}")
        return self

    @model_validator(mode="after")
    def _its_daily_commands_are_to_what_it_has(self) -> Self:
        known = {piece.actuator_id for piece in self.layout.equipment} | {
            opening.opening_id for opening in self.envelope.openings
        }
        unknown = sorted({c.actuator_id for c in self.daily} - known)
        if unknown:
            raise ValueError(f"daily commands to what it does not have: {', '.join(unknown)}")
        return self

    @model_validator(mode="after")
    def _its_control_runs_what_it_has(self) -> Self:
        control = self.control
        if control is None:
            return self
        if control.heating is not None:
            self._runs(control.heating.actuator_id, Heats, "heating loop", "heaters")
        if control.dehumidifying is not None:
            self._runs(
                control.dehumidifying.actuator_id,
                Dries,
                "dehumidifying loop",
                "dehumidifiers",
            )
        for fan in control.circulation.fans if control.circulation is not None else []:
            self._runs(fan, MovesAir, "circulation loop", "fans")
        vents = {o.opening_id for o in self.envelope.openings if o.kind != OpeningKind.DOOR}
        for vent in control.venting.vents if control.venting is not None else []:
            if vent not in vents:
                raise ValueError(f"a venting loop runs its vents, not {vent!r}")
        commanded = sorted({c.actuator_id for c in self.daily} & set(control.runs()))
        if commanded:
            them = "it" if len(commanded) == 1 else "them"
            raise ValueError(
                f"its control runs {', '.join(commanded)}: daily commands to {them} would take "
                f"{them} over"
            )
        later = [loop for loop in control.loops() if loop != "heating"]
        if later:
            raise ValueError(
                f"a scenario's control runs its heating loop alone until the house decides "
                f"every loop (P11.2), not its {', '.join(later)}"
            )
        return self

    def _runs(
        self, actuator_id: str, capability: type[Capability], loop: str, devices: str
    ) -> None:
        """Refuse a loop's device unless it is one of this scenario's
        equipment that does what the loop runs it for: a heating loop's
        heats, a dehumidifying loop's dries, a circulation loop's moves air
        (`greenhouse_sim.world.capabilities`)."""
        if not any(
            piece.actuator_id == actuator_id and can(piece, capability)
            for piece in self.layout.equipment
        ):
            raise ValueError(f"a {loop} runs one of its {devices}, not {actuator_id!r}")

    @property
    def thermostat(self) -> Thermostat | None:
        """The thermostat its runs follow: its control's heating loop, if it
        has one (`climate.control`)."""
        return None if self.control is None else self.control.thermostat()

    @model_validator(mode="after")
    def _every_plant_has_a_planting_position(self) -> Self:
        plants, positions = self.rows * self.columns, len(self.layout.planting_positions())
        if plants > positions:
            raise ValueError(f"{plants} plants, but only {positions} planting positions")
        return self
