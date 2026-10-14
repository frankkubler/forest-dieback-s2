import numpy as np

from forest_dieback.dataset import normalize, resample_series, spatial_block_split


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
