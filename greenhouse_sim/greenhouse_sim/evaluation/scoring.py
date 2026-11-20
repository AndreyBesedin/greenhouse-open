"""An episode's scores (P25.3, decisions 0081 and 0082): each measure's
value for one episode, from its record and from the run it carried out,
read once its policy has stopped.

- **A record's measure** is worked out from the episode's record as it was
  written (`measuring.record_values`): its actions by status, its
  decisions skipped and their times.
- **An instrument's measure** is worked out from the series the
  evaluator's instruments read of the run as carried out
  (`instruments.Instruments`, `measuring.series_value`): one value, or one
  for each device.
- **On no benchmark,** until an experiment names one (P25.4), an episode
  is scored on every definition the protocol packages, at each of its
  versions, and its scores name no benchmark. Its window is the whole
  episode, since no warm-up is stated. A measure against a goal's bounds,
  whose goal is a benchmark's, and the priced score, whose prices are a
  benchmark's, are not comparable, and say so; so is the harvest of a crop
  grown by area, which the instrument does not count.

Scores are a record of their own (`greenhouse_protocol.benchmark.
EpisodeScores`), beside the episode's and never inside its digest: the
record's digest, each value's measure by name, version and digest, and the
evaluator's software. The same record, the same run carried out and the
same definitions give the same scores.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from greenhouse_protocol.benchmark import (
    EpisodeScores,
    FromInstrument,
    FromMeasures,
    FromRecord,
    Instrument,
    MeasureDefinition,
    MeasureScored,
    MeasureValue,
    NotComparable,
    packaged_measures,
    scored,
)
from greenhouse_protocol.experiment import EpisodeRecord
from greenhouse_protocol.measuring import Interval, record_values, series_value

from greenhouse_sim.evaluation.instruments import Instruments
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.system import software

# Why a measure has no value on no benchmark, or for a crop grown by area.
NO_PRICES: Final = NotComparable(
    not_comparable="its prices are a benchmark's, and the episode is scored on none"
)
HARVEST_NOT_COUNTED: Final = NotComparable(
    not_comparable="its crop is grown by area, whose harvest the instrument does not count"
)


def score_episode(
    simulator: Simulator,
    record: EpisodeRecord,
    run: RunRequest,
    measures: Sequence[MeasureDefinition] | None = None,
) -> EpisodeScores:
    """An episode's scores on no benchmark, by `measures`, every packaged
    definition unless given: from `record`, as it was written, and `run`,
    the run it carried out (`experiment.carry_out_episode`), from its start
    to the episode's end. See the module. Refused as the instruments refuse
    a run, and beyond its end."""
    definitions = packaged_measures() if measures is None else measures
    end_s = record.run.episode_end_s
    instruments = Instruments(simulator, run, end_s)
    window = ((0.0, end_s),)
    return EpisodeScores(
        record_digest=record.digest,
        benchmark=None,
        measures=tuple(
            value
            for definition in definitions
            for value in _values(definition, record, instruments, window)
        ),
        software=software(),
    )


def _values(
    definition: MeasureDefinition,
    record: EpisodeRecord,
    instruments: Instruments,
    window: Sequence[Interval],
) -> list[MeasureScored]:
    """A measure's values for one episode: one, or one for each part it is
    broken down by."""
    given: Mapping[str | None, MeasureValue]
    match definition.source:
        case FromRecord():
            given = record_values(definition, record)
        case FromMeasures():
            given = {None: NO_PRICES}
        case FromInstrument() if definition.goal is not None:
            given = {
                None: NotComparable(
                    not_comparable=f"its goal {definition.goal!r} is a benchmark's,"
                    " and the episode is scored on none"
                )
            }
        case FromInstrument(instrument=Instrument.HARVEST) if not instruments.harvest_counted:
            given = {None: HARVEST_NOT_COUNTED}
        case FromInstrument() as source:
            given = {
                of: series_value(definition, samples, window, floor_area_m2=instruments.floor_m2)
                for of, samples in instruments.series(source).items()
            }
    return [scored(definition, value, of=of) for of, value in given.items()]
