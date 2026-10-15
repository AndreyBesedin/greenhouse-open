from datetime import UTC, date, datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

from greenhouse_sim.airflow.prescribed import PrescribedAirflow, UniformAirflow
from greenhouse_sim.cfd.setup import CfdSetup
from greenhouse_sim.climate.commands import DailyCommand
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import CropWork
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.weather.recorded import RecordedWeather
from greenhouse_sim.weather.sources import Clouded, ConstantWeather, RunWeather, Winded
from greenhouse_sim.weather.state import Percent
from greenhouse_sim.weather.synthetic import SyntheticWeather
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.layout import Layout, inside_the_greenhouse, outside_the_greenhouse
from greenhouse_sim.world.site import DEFAULT_SITE, Bearing, Site

# A refusal names this many of the things it refuses, and counts the rest.
NAMED_IN_A_REFUSAL = 3


class ScenarioConfig(BaseModel):
    """The simulated world: its greenhouse, crop, dynamics and sensor noise.

    Which management policy runs against it, and with what thresholds, is
    not part of the world. That is the caller's choice about a run.
    """

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
    crop_work: CropWork = CropWork()
    # The commands its runs give its equipment, doors and vents at a time of
    # day, every day, unless a run is given daily commands of its own (P09.4).
    daily: list[DailyCommand] = []
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
    # What its air starts from, and how it exchanges with the outside, in a
    # climate run, when its equipment drives it.
    climate: ClimateSettings = ClimateSettings()
    # Where it lies on the Earth, and the weather outside it.
    site: Site = DEFAULT_SITE
    weather: Annotated[
        ConstantWeather | SyntheticWeather | RecordedWeather, Field(discriminator="kind")
    ] = ConstantWeather()
    # A QA override of its weather's cloud cover, which dims its light as
    # such a sky would (`greenhouse_sim.weather.sources.Clouded`); none by
    # default.
    cloud_cover_pct: Percent | None = None
    # A QA override of its weather's wind direction, the compass bearing it
    # blows from (`greenhouse_sim.weather.sources.Winded`); none by default.
    wind_from_deg: Bearing | None = None

    # Environment: bounds the smooth day-to-day drift stays within.
    air_temperature_bounds: tuple[float, float] = (18.0, 32.0)
    humidity_bounds: tuple[float, float] = (45.0, 85.0)

    # Water reservoir / stress.
    initial_water_reservoir_ml: float = 600.0
    water_capacity_ml: PositiveFloat = 1200.0
    water_use_ml_per_day_base: float = 80.0
    evaporation_ml_per_day: float = 20.0
    water_stress_threshold_pct: float = 35.0

    # Stem / truss growth.
    initial_stem_length_cm: float = 20.0
    stem_growth_cm_per_day_base: float = 2.0
    truss_interval_days: PositiveInt = 6
    max_trusses: NonNegativeInt = 8
    fruits_per_truss_bounds: tuple[int, int] = (3, 6)

    # Fruit growth / ripening.
    target_diameter_mm_bounds: tuple[float, float] = (18.0, 26.0)
    fruit_growth_days_to_target: PositiveInt = 20
    mass_coefficient_g_per_mm3: float = 0.0012
    ripening_days_bounds: tuple[int, int] = (16, 26)

    # Observation noise (standard deviations / detection-error rates).
    soil_moisture_noise_pct: float = 3.0
    air_temperature_noise_c: float = 0.4
    fruit_count_noise_probability: float = 0.1
    ripe_mass_noise_pct: float = 8.0
    height_noise_cm: float = 1.5

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
    def _every_plant_has_a_planting_position(self) -> Self:
        plants, positions = self.rows * self.columns, len(self.layout.planting_positions())
        if plants > positions:
            raise ValueError(f"{plants} plants, but only {positions} planting positions")
        return self
