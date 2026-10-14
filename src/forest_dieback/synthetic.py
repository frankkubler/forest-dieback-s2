"""Séries synthétiques sain / attaqué pour les tests et la démo hors ligne.

Un pixel sain suit une saisonnalité harmonique du CRSWIR ; un pixel attaqué
voit son CRSWIR monter progressivement après une date d'attaque aléatoire,
comme le décrit FORDEAD.
"""

from __future__ import annotations

import numpy as np


def make_series(n: int = 2000, seq_len: int = 72, n_channels: int = 3,
                attacked_ratio: float = 0.3, seed: int = 0):
    rng = np.random.default_rng(seed)
    t = np.arange(seq_len)
    season = np.sin(2 * np.pi * t / 36.5)  # pas de 10 jours, période d'un an

    labels = (rng.random(n) < attacked_ratio).astype(np.float32)
    base = rng.normal(0, 0.05, (n, 1, n_channels))
    amp = rng.uniform(0.05, 0.15, (n, 1, n_channels))
    series = base + amp * season[None, :, None]
    series += rng.normal(0, 0.03, series.shape)

    onset = rng.integers(seq_len // 3, seq_len - 6, n)
    ramp = np.clip((t[None, :] - onset[:, None]) / 6.0, 0, 1)  # (n, T)
    # CRSWIR (canal 0) monte, NDVI et NDWI baissent
    signs = np.array([1.0] + [-1.0] * (n_channels - 1))
    series += labels[:, None, None] * 0.25 * ramp[:, :, None] * signs[None, None, :]

    x = rng.uniform(0, 20000, n)
    y = rng.uniform(0, 20000, n)
    return series.astype(np.float32), labels, x, y
