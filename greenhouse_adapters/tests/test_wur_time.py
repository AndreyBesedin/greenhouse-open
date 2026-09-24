from datetime import UTC, datetime

import pytest

from greenhouse_adapters.wur.common.time import matlab_datenum_to_utc

# datenum 739134 is 5 September 2023, the 2023 climate workbook's first day.
SEP_5 = 739134
# 29 October 2023: clocks go back at 03:00 CEST, so 02:00-02:59 happens twice
OCT_29 = SEP_5 + 54
# 26 March 2023: clocks go forward at 02:00 CET, so 02:00-02:59 never happens
MAR_26 = SEP_5 - 163


def test_summer_time_datenum_becomes_utc_two_hours_earlier() -> None:
    assert matlab_datenum_to_utc(SEP_5 + 0.5) == datetime(2023, 9, 5, 10, tzinfo=UTC)


def test_winter_time_datenum_becomes_utc_one_hour_earlier() -> None:
    assert matlab_datenum_to_utc(SEP_5 + 64.5) == datetime(2023, 11, 8, 11, tzinfo=UTC)


def test_float_noise_rounds_to_the_nearest_second() -> None:
    # a real cell from the workbook: 6 September 2023, 09:20 local
    assert matlab_datenum_to_utc(739135.388888889) == datetime(2023, 9, 6, 7, 20, tzinfo=UTC)


def test_the_repeated_autumn_hour_is_refused() -> None:
    with pytest.raises(ValueError, match="occurs twice"):
        matlab_datenum_to_utc(OCT_29 + 2.5 / 24)


def test_the_skipped_spring_hour_is_refused() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        matlab_datenum_to_utc(MAR_26 + 2.5 / 24)


def test_the_hours_either_side_of_the_autumn_change_are_accepted() -> None:
    assert matlab_datenum_to_utc(OCT_29 + 1.5 / 24) == datetime(2023, 10, 28, 23, 30, tzinfo=UTC)
    assert matlab_datenum_to_utc(OCT_29 + 3.5 / 24) == datetime(2023, 10, 29, 2, 30, tzinfo=UTC)
