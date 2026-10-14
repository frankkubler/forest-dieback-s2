"""Indices spectraux calculés sur les réflectances Sentinel-2.

Les fonctions acceptent des tableaux numpy (ou des DataArray xarray) de
réflectances, dans la même unité pour toutes les bandes.
"""

from __future__ import annotations

import numpy as np

# Longueurs d'onde centrales Sentinel-2 (nm), utilisées par le CRSWIR
WAVELENGTH = {"B8A": 864.7, "B11": 1613.7, "B12": 2202.4}

_EPS = 1e-6


def _safe_div(num, den):
    return num / np.where(np.abs(den) < _EPS, np.nan, den)


def ndvi(b8, b4):
    """Normalized Difference Vegetation Index."""
    return _safe_div(b8 - b4, b8 + b4)


def ndwi(b8a, b11):
    """NDWI de Gao (1996), sensible à la teneur en eau du couvert."""
    return _safe_div(b8a - b11, b8a + b11)


def crswir(b8a, b11, b12):
    """Continuum Removal in the SWIR, indice de FORDEAD.

    Rapport entre la réflectance B11 et le continuum interpolé linéairement
    entre B8A et B12 à la longueur d'onde de B11. Il augmente avec le stress
    hydrique des épicéas attaqués.
    """
    w8a, w11, w12 = WAVELENGTH["B8A"], WAVELENGTH["B11"], WAVELENGTH["B12"]
    continuum = b8a + (b12 - b8a) * (w11 - w8a) / (w12 - w8a)
    return _safe_div(b11, continuum)


def compute_indices(bands: dict, names=("CRSWIR", "NDVI", "NDWI")) -> dict:
    """Calcule les indices demandés à partir d'un dict {bande: tableau}."""
    funcs = {
        "CRSWIR": lambda b: crswir(b["B8A"], b["B11"], b["B12"]),
        "NDVI": lambda b: ndvi(b["B8"], b["B4"]),
        "NDWI": lambda b: ndwi(b["B8A"], b["B11"]),
    }
    unknown = set(names) - funcs.keys()
    if unknown:
        raise ValueError(f"Indices inconnus : {sorted(unknown)}")
    return {name: funcs[name](bands) for name in names}
