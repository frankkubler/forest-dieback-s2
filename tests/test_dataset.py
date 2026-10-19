import numpy as np

from forest_dieback.dataset import (
    cube_to_indices,
    interpolate_gaps,
    mask_implausible,
    normalize,
    resample_series,
    scale_reflectance,
    spatial_block_split,
)


def test_resample_interpolates_and_skips_nan():
    dates = np.array([0, 10, 20, 30])
    values = np.array([[0.0], [np.nan], [2.0], [3.0]])
    out = resample_series(dates, values, np.array([0, 10, 30]))
    np.testing.assert_allclose(out[:, 0], [0.0, 1.0, 3.0])


def test_block_split_keeps_blocks_together():
    rng = np.random.default_rng(0)
    x, y = rng.uniform(0, 10000, 5000), rng.uniform(0, 10000, 5000)
    split = spatial_block_split(x, y, 1000, {"train": 0.7, "val": 0.15, "test": 0.15})
    blocks = np.floor(x / 1000).astype(int) * 100 + np.floor(y / 1000).astype(int)
    for b in np.unique(blocks):
        assert len(set(split[blocks == b])) == 1
    assert set(split) == {"train", "val", "test"}


def test_normalize_fills_nan():
    s = np.array([[[1.0], [np.nan]], [[3.0], [5.0]]])
    out, mean, std = normalize(s)
    assert not np.isnan(out).any()
    assert mean.shape == (1,)


def test_long_table_to_cube_fills_missing_with_nan():
    import pandas as pd

    from forest_dieback.dataset import long_table_to_cube

    df = pd.DataFrame({
        "x": [0, 0, 10],
        "y": [5, 5, 5],
        "date": ["2023-01-01", "2023-01-11", "2023-01-11"],
        "B4": [1.0, 2.0, 3.0],
        "B8": [4.0, 5.0, 6.0],
    })
    cube, ids, dates = long_table_to_cube(
        df, ["B4", "B8"], dates=["2023-01-01", "2023-01-11", "2023-01-21"])
    assert cube.shape == (2, 3, 2)
    assert list(ids["x"]) == [0, 10]
    np.testing.assert_allclose(cube[0, :2], [[1, 4], [2, 5]])
    assert np.isnan(cube[1, 0]).all() and np.isnan(cube[:, 2]).all()
    assert len(dates) == 3


def test_scale_reflectance_turns_nodata_into_nan():
    cube = np.array([[[0, 1500, 2000]]], dtype=np.uint16)
    out = scale_reflectance(cube)
    assert np.isnan(out[0, 0, 0])            # le 0 de GEE est un trou
    np.testing.assert_allclose(out[0, 0, 1:], [0.15, 0.20])


def test_cube_to_indices_puts_crswir_first():
    bands = ["B4", "B8", "B8A", "B11", "B12"]
    cube = np.full((2, 3, 5), 0.2, dtype=np.float32)
    out = cube_to_indices(cube, bands, ["CRSWIR", "NDVI", "NDWI"])
    assert out.shape == (2, 3, 3)
    # bandes égales : le continuum vaut B11, donc CRSWIR = 1 ; NDVI et NDWI = 0
    np.testing.assert_allclose(out[..., 0], 1.0, atol=1e-5)
    np.testing.assert_allclose(out[..., 1:], 0.0, atol=1e-5)


def test_cube_to_indices_refuses_a_band_count_mismatch():
    import pytest
    with pytest.raises(ValueError, match="bandes"):
        cube_to_indices(np.zeros((1, 2, 3)), ["B4", "B8", "B8A", "B11", "B12"], ["NDVI"])


def test_interpolate_gaps_fills_cloudy_dates():
    cube = np.array([[[0.0], [np.nan], [2.0]]], dtype=np.float32)
    out = interpolate_gaps(cube, np.array([0.0, 10.0, 20.0]))
    np.testing.assert_allclose(out[0, :, 0], [0.0, 1.0, 2.0])


def test_mask_implausible_only_touches_bounded_channels():
    series = np.array([[[67.0, 0.5], [0.8, 0.5], [-1.0, 9.9]]], dtype=np.float32)
    out = mask_implausible(series, ["CRSWIR", "NDVI"], {"CRSWIR": [0.0, 2.0]})
    assert np.isnan(out[0, 0, 0]) and np.isnan(out[0, 2, 0])  # 67 et -1 écartés
    assert out[0, 1, 0] == 0.8                                 # la valeur plausible reste
    assert out[0, 2, 1] == 9.9                                 # NDVI non borné : intact


def test_mask_implausible_without_ranges_is_a_noop():
    series = np.array([[[67.0]]], dtype=np.float32)
    np.testing.assert_array_equal(mask_implausible(series, ["CRSWIR"], None), series)
