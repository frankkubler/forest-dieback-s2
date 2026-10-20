from datetime import date

from forest_dieback.grid import (
    band_names,
    bbox_shape,
    coverage_summary,
    estimate_bytes,
    split_bbox,
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


def test_coverage_summary_separates_the_growing_season():
    periods = year_periods(2022, 10)
    # 0 % en janvier et février, 100 % le reste de l'année
    fractions = [0.0 if start.month <= 2 else 1.0 for start, _ in periods]
    c = coverage_summary(periods, fractions)
    assert c["n_total"] == 37
    assert c["n_poor"] == 6          # les six composites de janvier et février
    assert c["n_season"] == 19       # avril à septembre
    assert c["season_mean"] == 1.0   # la saison utile est intacte
    assert 0.8 < c["mean"] < 0.85    # alors que la moyenne annuelle est entamée


def test_coverage_summary_handles_a_year_without_any_composite():
    assert coverage_summary([], []) == {
        "mean": 0.0, "season_mean": 0.0, "n_season": 0, "n_poor": 0, "n_total": 0,
    }


def test_split_bbox_covers_the_whole_area_without_overlap():
    bbox = [6.88, 47.75, 7.15, 47.93]
    fenetres = split_bbox(bbox, 2)
    assert len(fenetres) == 4
    assert {ij for ij, _ in fenetres} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    # les bords extrêmes des fenêtres redonnent l'emprise de départ
    lons = [v for _, f in fenetres for v in (f[0], f[2])]
    lats = [v for _, f in fenetres for v in (f[1], f[3])]
    assert (min(lons), max(lons)) == (bbox[0], bbox[2])
    assert (min(lats), max(lats)) == (bbox[1], bbox[3])
    # la somme des surfaces égale celle de l'emprise : ni trou, ni recouvrement
    aire = sum((f[2] - f[0]) * (f[3] - f[1]) for _, f in fenetres)
    assert abs(aire - (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) < 1e-12


def test_split_bbox_of_one_returns_the_area_unchanged():
    bbox = [6.88, 47.75, 7.15, 47.93]
    fenetres = split_bbox(bbox, 1)
    assert len(fenetres) == 1
    (ij, f), = fenetres
    assert ij == (0, 0)
    assert f == bbox


def test_split_bbox_refuses_an_empty_grid():
    import pytest
    with pytest.raises(ValueError, match="au moins une"):
        split_bbox([0, 0, 1, 1], 0)
