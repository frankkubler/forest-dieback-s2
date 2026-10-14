import numpy as np
import pytest

from forest_dieback.indices import compute_indices, crswir, ndvi, ndwi


def test_ndvi_bounds():
    assert ndvi(np.array(0.4), np.array(0.04)) == pytest.approx(0.818, abs=1e-3)
    assert np.isnan(ndvi(np.array(0.0), np.array(0.0)))


def test_ndwi_sign():
    assert ndwi(np.array(0.35), np.array(0.15)) > 0


def test_crswir_is_one_on_linear_continuum():
    b8a, b12 = 0.3, 0.1
    # B11 exactement sur la droite B8A–B12 → CRSWIR = 1
    b11 = b8a + (b12 - b8a) * (1613.7 - 864.7) / (2202.4 - 864.7)
    assert crswir(np.array(b8a), np.array(b11), np.array(b12)) == pytest.approx(1.0)


def test_crswir_rises_with_water_stress():
    healthy = crswir(np.array(0.30), np.array(0.15), np.array(0.07))
    stressed = crswir(np.array(0.25), np.array(0.20), np.array(0.12))
    assert stressed > healthy


def test_compute_indices_rejects_unknown():
    with pytest.raises(ValueError):
        compute_indices({}, names=("EVI",))
