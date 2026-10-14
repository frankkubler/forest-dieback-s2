"""Construction du jeu d'entraînement et découpage spatial par blocs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset


def resample_series(dates: np.ndarray, values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Interpole une série irrégulière (T, C) sur une grille de dates régulière.

    ``dates`` et ``grid`` sont en jours ; les NaN (dates masquées) sont ignorés
    canal par canal. Un canal sans aucune observation reste à NaN.
    """
    out = np.full((len(grid), values.shape[1]), np.nan, dtype=np.float32)
    for c in range(values.shape[1]):
        ok = ~np.isnan(values[:, c])
        if ok.sum() >= 2:
            out[:, c] = np.interp(grid, dates[ok], values[ok, c])
        elif ok.sum() == 1:
            out[:, c] = values[ok, c][0]
    return out


def long_table_to_cube(df: pd.DataFrame, bands: list[str], dates=None,
                       id_cols: tuple[str, ...] = ("x", "y")):
    """Table longue exportée de GEE (une ligne par pixel et par date) -> cube.

    Renvoie le cube (N, T, C), les identifiants des pixels (N lignes) et les
    dates (T). Les couples (pixel, date) absents de la table (nuages,
    composite vide) valent NaN. ``dates`` impose la grille temporelle ; par
    défaut, toutes les dates présentes dans la table.
    """
    df = df.assign(date=pd.to_datetime(df["date"]))
    if dates is None:
        dates = sorted(df["date"].unique())
    dates = pd.DatetimeIndex(pd.to_datetime(dates))
    ids = df[list(id_cols)].drop_duplicates().sort_values(list(id_cols)).reset_index(drop=True)
    grid = ids.merge(pd.DataFrame({"date": dates}), how="cross")
    values = (
        df.set_index([*id_cols, "date"])[bands]
        .reindex(pd.MultiIndex.from_frame(grid))
        .to_numpy(dtype=np.float32)
    )
    return values.reshape(len(ids), len(dates), len(bands)), ids, dates


def spatial_block_split(
    x: np.ndarray,
    y: np.ndarray,
    block_size: float,
    fractions: dict[str, float],
    seed: int = 42,
) -> np.ndarray:
    """Attribue chaque pixel à 'train', 'val' ou 'test' selon son bloc spatial.

    Tous les pixels d'un même bloc carré partagent le même ensemble, ce qui
    évite qu'un modèle soit évalué sur des voisins immédiats de ses pixels
    d'entraînement (autocorrélation spatiale).
    """
    bx = np.floor(np.asarray(x) / block_size).astype(np.int64)
    by = np.floor(np.asarray(y) / block_size).astype(np.int64)
    block_ids, inverse = np.unique(np.stack([bx, by], axis=1), axis=0, return_inverse=True)

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(block_ids))
    n_train = int(round(fractions["train"] * len(block_ids)))
    n_val = int(round(fractions["val"] * len(block_ids)))

    block_split = np.empty(len(block_ids), dtype=object)
    block_split[order[:n_train]] = "train"
    block_split[order[n_train:n_train + n_val]] = "val"
    block_split[order[n_train + n_val:]] = "test"
    return block_split[inverse.ravel()]


def normalize(series: np.ndarray, mean: np.ndarray | None = None, std: np.ndarray | None = None):
    """Standardise par canal (N, T, C) ; renvoie aussi les statistiques."""
    if mean is None:
        mean = np.nanmean(series, axis=(0, 1))
        std = np.nanstd(series, axis=(0, 1)) + 1e-6
    out = (series - mean) / std
    return np.nan_to_num(out, nan=0.0).astype(np.float32), mean, std


class PixelSeriesDataset(Dataset):
    """Séries par pixel (N, T, C) et étiquettes binaires (0 sain, 1 attaqué)."""

    def __init__(self, series: np.ndarray, labels: np.ndarray):
        self.series = torch.as_tensor(series, dtype=torch.float32)
        self.labels = torch.as_tensor(labels, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, i):
        return self.series[i], self.labels[i]
