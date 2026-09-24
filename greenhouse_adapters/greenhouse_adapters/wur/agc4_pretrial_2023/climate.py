"""ClimateTimeseries.xlsx -> canonical Observations.

Sheet `weather_climate` has one row per 5 minutes, 5 September to 9 November
2023, timestamped by a MATLAB datenum in Dutch local wall-clock time. The
daily radiation peak moves an hour earlier after 29 October, and the export
leaves that night's repeated 02:00-03:00 hour empty. Missing values are NaN.

Column names in the data differ from the workbook's own Info sheet in places
(`part1` for `par1`, `scr_enrg` for `scr_enr`, `vent_lee` for `wind_lee`); the
maps below use the data's names.

Weather columns describe the site and name no compartment; greenhouse columns
describe the pre-trial compartment. `rain` is a share of the 5-minute interval
(32 distinct values between 0 and 1), not a 0/1 state. `t_rail`, the rail
pipe, is the lower heating circuit, the same pipe the 2024 data calls
`heating_lower_circuit/pipe_temperature`.

Deliberately not ingested: `par1`-`par4`, PAR per light-treatment zone - zones
inside the compartment, which need the spatial region model - and `ligth_on`,
which the Info sheet does not document and which is fractional."""

from collections.abc import Iterator
from typing import IO

import openpyxl
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_adapters.wur.agc4_pretrial_2023 import SOURCE_ID
from greenhouse_adapters.wur.agc4_pretrial_2023.compartments import COMPARTMENT_ID, GREENHOUSE_ID
from greenhouse_adapters.wur.common.cells import number_cell
from greenhouse_adapters.wur.common.time import matlab_datenum_to_utc

SHEET = "weather_climate"
DATENUM_COLUMN = "datenum"
SOURCE = RecordSource(type=SourceType.IMPORTED_DATA, source_id=SOURCE_ID)

WEATHER_CHANNELS: dict[str, ObservationType] = {
    "tout": ObservationType.OUTSIDE_AIR_TEMPERATURE_C,
    "rhout": ObservationType.OUTSIDE_RELATIVE_HUMIDITY_PCT,
    "iglob": ObservationType.OUTSIDE_GLOBAL_RADIATION_W_M2,
    "windsp": ObservationType.OUTSIDE_WIND_SPEED_M_S,
    "rain": ObservationType.OUTSIDE_RAIN,
    "parout": ObservationType.OUTSIDE_PAR_UMOL_M2_S,
    "pyrgeo": ObservationType.OUTSIDE_HEAT_EMISSION_W_M2,
    "co2out": ObservationType.OUTSIDE_CO2_PPM,
}

COMPARTMENT_CHANNELS: dict[str, ObservationType] = {
    "t_air": ObservationType.AIR_TEMPERATURE_C,
    "rh": ObservationType.RELATIVE_HUMIDITY_PCT,
    "co2": ObservationType.CO2_PPM,
    "scr_enrg": ObservationType.ENERGY_SCREEN_POSITION_PCT,
    "scr_blck": ObservationType.BLACKOUT_SCREEN_POSITION_PCT,
    "vent_lee": ObservationType.WINDOW_POSITION_LEE_PCT,
    "vent_wind": ObservationType.WINDOW_POSITION_WIND_PCT,
    "t_rail": ObservationType.HEATING_PIPE_TEMPERATURE_C,
}


def parse_climate(source: IO[bytes]) -> Iterator[Observation]:
    """Observations in row order (chronological in the source). Rows with no
    value at all - the export's padding and the repeated DST hour - are
    skipped before their timestamp is read."""
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        rows = workbook[SHEET].iter_rows(values_only=True)
        header = [str(cell).strip() if cell is not None else "" for cell in next(rows)]
        expected = {DATENUM_COLUMN, *WEATHER_CHANNELS, *COMPARTMENT_CHANNELS}
        missing = sorted(expected - set(header))
        if missing:
            raise ValueError(f"{SHEET} is missing columns {missing}")
        datenum_index = header.index(DATENUM_COLUMN)
        mapped = [
            (header.index(column), observation_type, None, "site")
            for column, observation_type in WEATHER_CHANNELS.items()
        ] + [
            (header.index(column), observation_type, COMPARTMENT_ID, COMPARTMENT_ID)
            for column, observation_type in COMPARTMENT_CHANNELS.items()
        ]

        for row in rows:
            values = [
                (observation_type, compartment_id, scope, value)
                for index, observation_type, compartment_id, scope in mapped
                if (value := number_cell(row, index)) is not None
            ]
            if not values:
                continue
            datenum = number_cell(row, datenum_index)
            if datenum is None:
                raise ValueError(f"{SHEET}: a row with readings has no datenum")
            timestamp = matlab_datenum_to_utc(datenum)
            stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
            for observation_type, compartment_id, scope, value in values:
                yield Observation(
                    observation_id=f"wur23_{scope}_{stamp}_{observation_type.value}",
                    greenhouse_id=GREENHOUSE_ID,
                    compartment_id=compartment_id,
                    plant_id=None,
                    timestamp=timestamp,
                    observation_type=observation_type,
                    value=value,
                    source=SOURCE,
                )
    finally:
        workbook.close()
