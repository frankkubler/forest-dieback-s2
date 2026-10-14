from datetime import date

from forest_dieback.grid import (
    band_names,
    bbox_shape,
    estimate_bytes,
    year_periods,
    years_in_range,
)


def test_year_periods_cover_the_year_without_overlap():
    periods = year_periods(2023, 10)
    assert len(periods) == 37
    assert periods[0] == (date(2023, 1, 1), date(2023, 1, 11))
    assert periods[-1] == (date(2023, 12, 27), date(2024, 1, 1))
    for (_, end), (start, _) in zip(periods, periods[1:], strict=False):
        assert end == start


def test_year_periods_are_clipped_to_the_configured_range():
    periods = year_periods(2026, 10, "2017-01-01", "2026-10-01")
    assert periods[-1] == (date(2026, 9, 28), date(2026, 10, 1))
    assert year_periods(2016, 10, "2017-01-01", "2026-10-01") == []


def test_years_in_range_excludes_exclusive_end():
    assert years_in_range("2017-01-01", "2026-10-01") == list(range(2017, 2027))
    assert years_in_range("2017-01-01", "2018-01-01") == [2017]


def test_band_names_follow_tobands_order():
    periods = year_periods(2023, 10)[:2]
    assert band_names(periods, ["B4", "B8"]) == [
        "20230101_B4", "20230101_B8", "20230111_B4", "20230111_B8"]


def test_bbox_shape_of_study_area():
    cols, rows = bbox_shape([6.88, 47.75, 7.15, 47.93], 10)
    assert 1950 < cols < 2100 and 1950 < rows < 2100


def test_estimate_bytes():
    assert estimate_bytes(100, 3, 5) == 3000
