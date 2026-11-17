"""A benchmark's measures, and an episode's scores (P25, decision 0081).

A measure is a definition before it is a number: a packaged file, read
through `MeasureDefinition`, which names

- **its name and version:** a published version never changes, and a
  correction is a new version;
- **its class** (`MeasureClass`): `climate`, `record` (what the episode's
  record alone says), `crop`, `economic`, or `priced` (other measures
  weighed in money);
- **what it measures,** its unit and its denominators, and what its value
  is broken down by, if anything (each device, each status);
- **its window and aggregation:** over the episode, or the episode less the
  warm-up its benchmark states; summed, integrated through time, counted,
  or a quantile; for a constraint, the benchmark's goal whose bounds and
  hours it is scored against; and how a quantity sampled through time is
  taken between its samples;
- **its source:** a field of the episode's record, one of the evaluator's
  instruments by name (decision 0082), or, for a priced score, the
  measures it weighs, each at a price of its benchmark's, by name;
- **what it leaves out,** in words;
- **its digest** (`MeasureDefinition.digest`): the SHA-256 of its JSON,
  keys sorted, as an episode's settings are digested.

An episode's scores (`EpisodeScores`) are a record of their own, beside the
episode's and never inside its digest: the record's digest, the benchmark's
name, version and digest, each measure's name, version, digest and value,
and the evaluator's software. A value is a number, or *not comparable* with
its reason (`NotComparable`).

What a benchmark of a class compares, and what it may only report, is
`refused_by_class`'s rule. The arithmetic each definition implies is in
`greenhouse_protocol.measuring`.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from functools import cache
from importlib.resources import files
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.budget import Name, Sha256
from greenhouse_protocol.experiment import Software, settings_sha256

# The formats of a definition and of an episode's scores, changed when a
# reader of the last could misread them.
MEASURE_DEFINITION_VERSION: Final = 1
EPISODE_SCORES_VERSION: Final = 1
# A measure's name, as its file and every score name it: lower case words
# joined by hyphens.
type MeasureName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
# The packaged definitions' folder in the package, one file a version,
# named `<name>.v<version>.json`.
MEASURES_DIR: Final = "measures"


class MeasureClass(StrEnum):
    CLIMATE = "climate"  # the house's air, its heat and its equipment
    RECORD = "record"  # what the episode's record alone says
    CROP = "crop"  # the crop model's outputs: predictions
    ECONOMIC = "economic"  # fuel, electricity, cost, margin: not modelled yet
    PRICED = "priced"  # other measures weighed in money


class Per(StrEnum):
    """What a measure's value is divided by."""

    FLOOR_M2 = "floor_m2"  # the house's floor area, in m²
    DAY = "day"  # the days its window lasts


class By(StrEnum):
    """What a measure's value is broken down by, one value each."""

    DEVICE = "device"
    STATUS = "status"  # an action's outcome's status


class MeasureWindow(StrEnum):
    EPISODE = "episode"  # from the episode's start to its end
    AFTER_WARM_UP = "after_warm_up"  # less the warm-up its benchmark states


class Aggregation(StrEnum):
    """How a measure makes one value of its source, over its window."""

    # The amounts given at moments within the window, summed.
    TOTAL = "total"
    # The quantity integrated through time, in its unit-hours.
    INTEGRAL = "integral"
    # The hours the quantity is outside its goal's bounds.
    HOURS_OUTSIDE = "hours_outside"
    # How far outside its goal's bounds the quantity is, integrated through
    # time, in its unit-hours.
    INTEGRAL_OUTSIDE = "integral_outside"
    # The times the quantity changes value within the window.
    CHANGES = "changes"
    # The records counted: those true, or those of each kind it is by.
    COUNT = "count"
    # A quantile of the values, by linear interpolation between the closest
    # ranks; 0.5 the median, 1 the largest.
    QUANTILE = "quantile"
    # The measures it weighs, each times its price, summed.
    WEIGHTED_SUM = "weighted_sum"


# The aggregations of a quantity through time, and those against a goal's bounds.
THROUGH_TIME: Final = frozenset(
    {Aggregation.INTEGRAL, Aggregation.HOURS_OUTSIDE, Aggregation.INTEGRAL_OUTSIDE}
)
AGAINST_A_GOAL: Final = frozenset({Aggregation.HOURS_OUTSIDE, Aggregation.INTEGRAL_OUTSIDE})


class BetweenSamples(StrEnum):
    """How a quantity sampled through time is taken between its samples."""

    # Each sample's value holds until the next, the last until the window's end.
    HELD = "held"


class RecordField(StrEnum):
    """A field of the episode's record a `record` measure is made from."""

    OUTCOME_STATUS = "outcomes.status"
    DECISION_SKIPPED = "trace.skipped"
    DECISION_TIME = "trace.took_s"


class Instrument(StrEnum):
    """The evaluator's instruments, which read an episode's truth once its
    policy has stopped (decision 0082)."""

    HOUSE_AIR = "house_air"  # the house's air through time, every minute
    HEAT_GIVEN = "heat_given"  # the heaters' heat to the air
    EQUIPMENT_STATES = "equipment_states"  # each device's level, and its switches
    HARVEST = "harvest"  # the run's harvest events


class FromRecord(BaseModel):
    """A measure made from a field of the episode's record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["record"] = "record"
    field: RecordField


class FromInstrument(BaseModel):
    """A measure made from one quantity of one of the evaluator's instruments,
    such as the house air's `temperature`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["instrument"] = "instrument"
    instrument: Instrument
    quantity: Identifier


class MeasureNamed(BaseModel):
    """A measure as another names it: its name and version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: MeasureName
    version: PositiveInt


class PricedTerm(BaseModel):
    """One measure a priced score weighs, at its benchmark's price by name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    measure: MeasureNamed
    price: Identifier


class FromMeasures(BaseModel):
    """A priced score's source: the measures it weighs, each at its price."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["measures"] = "measures"
    terms: Annotated[tuple[PricedTerm, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _each_measure_once(self) -> Self:
        named = [term.measure for term in self.terms]
        if len(set(named)) != len(named):
            raise ValueError("a priced score weighs each measure once")
        return self


type MeasureSource = Annotated[
    FromRecord | FromInstrument | FromMeasures, Field(discriminator="kind")
]


class MeasureDefinition(BaseModel):
    """A measure, as its file defines it: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    definition_version: Literal[1] = MEASURE_DEFINITION_VERSION
    name: MeasureName
    version: PositiveInt
    measure_class: MeasureClass
    description: Name
    unit: Name
    per: tuple[Per, ...] = ()
    by: By | None = None
    window: MeasureWindow
    aggregation: Aggregation
    # The quantile it takes, for a quantile alone.
    quantile: Annotated[float, Field(ge=0, le=1)] | None = None
    # The benchmark's constraint whose bounds, and hours of the day, it is
    # scored against, for an aggregation against a goal alone.
    goal: Identifier | None = None
    # For an aggregation through time alone.
    between_samples: BetweenSamples | None = None
    source: MeasureSource
    leaves_out: Name

    @model_validator(mode="after")
    def _its_parts_agree(self) -> Self:
        priced = self.measure_class == MeasureClass.PRICED
        if priced != isinstance(self.source, FromMeasures):
            raise ValueError("a priced measure, and it alone, weighs other measures")
        if priced != (self.aggregation == Aggregation.WEIGHTED_SUM):
            raise ValueError("a priced measure, and it alone, is a weighted sum")
        if (self.measure_class == MeasureClass.RECORD) != isinstance(self.source, FromRecord):
            raise ValueError("a record measure, and it alone, is made from the record")
        if isinstance(self.source, FromRecord) and self.window != MeasureWindow.EPISODE:
            raise ValueError("a record measure is over the whole episode")
        if (self.aggregation == Aggregation.QUANTILE) != (self.quantile is not None):
            raise ValueError("a quantile, and it alone, names the quantile it takes")
        if (self.aggregation in AGAINST_A_GOAL) != (self.goal is not None):
            raise ValueError("a measure against a goal's bounds, and it alone, names its goal")
        if (self.aggregation in THROUGH_TIME) != (self.between_samples is not None):
            raise ValueError(
                "a measure through time, and it alone, says how it is taken between samples"
            )
        if len(set(self.per)) != len(self.per):
            raise ValueError("a measure is divided by each denominator once")
        return self

    @property
    def named(self) -> MeasureNamed:
        return MeasureNamed(name=self.name, version=self.version)

    @property
    def digest(self) -> str:
        """The SHA-256 of its JSON, every field written and keys sorted, as an
        episode's settings are digested: that of its packaged file, which
        writes every field."""
        return settings_sha256(self.model_dump(mode="json"))


def read_measure(text: str) -> MeasureDefinition:
    """A definition from its file's JSON."""
    return MeasureDefinition.model_validate_json(text)


@cache
def packaged_measures() -> tuple[MeasureDefinition, ...]:
    """The definitions packaged with the protocol, by name then version; each
    file is named for its definition's name and version."""
    measures = []
    for path in files("greenhouse_protocol").joinpath(MEASURES_DIR).iterdir():
        if not path.name.endswith(".json"):
            continue
        measure = read_measure(path.read_text(encoding="utf-8"))
        if path.name != f"{measure.name}.v{measure.version}.json":
            raise ValueError(f"{path.name} defines {measure.name} version {measure.version}")
        measures.append(measure)
    return tuple(sorted(measures, key=lambda measure: (measure.name, measure.version)))


def packaged_measure(name: str, version: int) -> MeasureDefinition:
    """One packaged definition, by name and version."""
    for measure in packaged_measures():
        if (measure.name, measure.version) == (name, version):
            return measure
    raise KeyError(f"no packaged measure {name!r} at version {version}")


class NotComparable(BaseModel):
    """A value a measure cannot give with a common basis, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    not_comparable: Name


type MeasureValue = FiniteFloat | NotComparable


class MeasureScored(BaseModel):
    """A measure's value for an episode: the measure by name, version and
    digest, what the value is of when the measure is broken down (a device's
    id, a status), and the value."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: MeasureName
    version: PositiveInt
    digest: Sha256
    of: Name | None = None
    value: MeasureValue


class BenchmarkNamed(BaseModel):
    """A benchmark as a score names it: its name, version and digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Name
    version: PositiveInt
    digest: Sha256


class EpisodeScores(BaseModel):
    """An episode's scores: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scores_version: Literal[1] = EPISODE_SCORES_VERSION
    record_digest: Sha256
    benchmark: BenchmarkNamed
    measures: tuple[MeasureScored, ...]
    software: Software

    @model_validator(mode="after")
    def _one_value_each(self) -> Self:
        keys = [(scored.name, scored.version, scored.of) for scored in self.measures]
        if len(set(keys)) != len(keys):
            raise ValueError("an episode's scores give each measure one value, or one per part")
        digests: dict[tuple[str, int], str] = {}
        for scored in self.measures:
            if digests.setdefault((scored.name, scored.version), scored.digest) != scored.digest:
                raise ValueError(f"measure {scored.name!r} is named with two digests")
        return self


def scored(
    definition: MeasureDefinition, value: MeasureValue, *, of: str | None = None
) -> MeasureScored:
    """A value, named with the definition that gave it."""
    return MeasureScored(
        name=definition.name,
        version=definition.version,
        digest=definition.digest,
        of=of,
        value=value,
    )


class BenchmarkClass(StrEnum):
    """What a benchmark compares. Crop and economic benchmarks wait for crop
    models validated (decision 0060) and measures that state their basis
    (decision 0062)."""

    CLIMATE = "climate"


class MeasureRole(StrEnum):
    COMPARED = "compared"  # compared, ranked and priced across policies
    REPORTED = "reported"  # shown beside each policy's scores, never compared


# What a benchmark of each class compares, and what it may only report.
COMPARED_IN: Final[Mapping[BenchmarkClass, frozenset[MeasureClass]]] = {
    BenchmarkClass.CLIMATE: frozenset(
        {MeasureClass.CLIMATE, MeasureClass.RECORD, MeasureClass.PRICED}
    ),
}
REPORTED_IN: Final[Mapping[BenchmarkClass, frozenset[MeasureClass]]] = {
    BenchmarkClass.CLIMATE: COMPARED_IN[BenchmarkClass.CLIMATE] | {MeasureClass.CROP},
}


def refused_by_class(
    benchmark_class: BenchmarkClass,
    measures: Sequence[tuple[MeasureDefinition, MeasureRole]],
) -> tuple[str, ...]:
    """Why a benchmark of its class may not name its measures as it does:
    nothing when it may. A measure is compared only if its class is one the
    benchmark's compares, and reported only if its class is one it may
    report; a priced measure weighs only measures the benchmark names and
    compares the class of, so a crop's prediction is never priced."""
    named = {definition.named: definition for definition, _ in measures}
    refusals = []
    for definition, role in measures:
        allowed = (COMPARED_IN if role == MeasureRole.COMPARED else REPORTED_IN)[benchmark_class]
        if definition.measure_class not in allowed:
            refusals.append(
                f"a {benchmark_class} benchmark does not take {definition.name!r},"
                f" of the {definition.measure_class} class, as {role}"
            )
        if isinstance(definition.source, FromMeasures):
            for term in definition.source.terms:
                weighed = named.get(term.measure)
                if weighed is None:
                    refusals.append(
                        f"{definition.name!r} weighs {term.measure.name!r} version"
                        f" {term.measure.version}, which the benchmark does not name"
                    )
                elif weighed.measure_class not in COMPARED_IN[benchmark_class]:
                    refusals.append(
                        f"{definition.name!r} weighs {weighed.name!r}, of the"
                        f" {weighed.measure_class} class, which a {benchmark_class} benchmark"
                        " does not compare"
                    )
    return tuple(refusals)
