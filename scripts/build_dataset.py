"""Étape 4 : assemble les CSV exportés de GEE en jeu d'entraînement.

    python scripts/build_dataset.py                        # sans étiquettes
    python scripts/build_dataset.py --labels data/raw/fordead/zones.gpkg

Lit les tables longues ``samples_<zone>_<année>.csv`` rapatriées depuis
Drive, les empile sur une grille temporelle régulière, en tire les indices
spectraux et écrit ``data/processed/dataset.npz`` : ``series`` (N, T, C),
``labels``, ``x``, ``y``, ``dates``, ``channels`` et ``split``.

Sans ``--labels``, toutes les étiquettes valent 0 : le cube est utilisable
pour inspecter les séries, pas pour entraîner.
"""

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from forest_dieback.config import load_config
from forest_dieback.dataset import (
    cube_to_indices,
    interpolate_gaps,
    long_table_to_cube,
    mask_implausible,
    scale_reflectance,
    spatial_block_split,
)
from forest_dieback.grid import year_periods, years_in_range


def composite_dates(cfg: dict) -> list:
    """Grille régulière des débuts de composite, toutes années confondues."""
    s2c = cfg["sentinel2"]
    dates = []
    for year in years_in_range(s2c["start_date"], s2c["end_date"]):
        periods = year_periods(year, s2c["composite_days"], s2c["start_date"], s2c["end_date"])
        dates += [start for start, _ in periods]
    return sorted(dates)


def read_tables(paths: list[Path], bands: list[str], round_m: int) -> pd.DataFrame:
    """Concatène les CSV annuels en une seule table longue.

    Les coordonnées sont arrondies pour que les mêmes pixels se retrouvent
    d'une année à l'autre malgré le formatage décimal des CSV.
    """
    frames = []
    for path in paths:
        df = pd.read_csv(path)
        missing = {"x", "y", "date", *bands} - set(df.columns)
        if missing:
            raise SystemExit(f"{path} : colonnes manquantes {sorted(missing)}")
        frames.append(df[["x", "y", "date", *bands]])
    df = pd.concat(frames, ignore_index=True)
    df[["x", "y"]] = df[["x", "y"]].round(round_m)
    return df


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=None)
    p.add_argument("--samples-dir", type=Path, default=None,
                   help="dossier des CSV (défaut : paths.raw/s2)")
    p.add_argument("--glob", default="samples_*.csv")
    p.add_argument("--labels", default=None,
                   help="motif des cartes de dépérissement (défaut : labels.dieback_maps)")
    p.add_argument("--no-labels", action="store_true",
                   help="ignorer les cartes, toutes les étiquettes à 0")
    p.add_argument("--until", default=None,
                   help="ne garder que les composites avant cette date "
                        "(défaut : labels.dieback_until)")
    p.add_argument("--no-interpolate", action="store_true",
                   help="laisser les trous nuageux en NaN")
    p.add_argument("--round-m", type=int, default=0,
                   help="arrondi des coordonnées, en décimales")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    cfg = load_config(args.config)
    bands = cfg["sentinel2"]["bands"]
    names = cfg["indices"]

    src = args.samples_dir or Path(cfg["paths"]["raw"]) / "s2"
    paths = sorted(src.glob(args.glob))
    if not paths:
        raise SystemExit(
            f"Aucun fichier « {args.glob} » dans {src}/.\n"
            "Rapatrier depuis Drive les CSV produits par « make extract-samples »."
        )
    print(f"{len(paths)} fichiers lus dans {src}/")

    df = read_tables(paths, bands, args.round_m)
    dates = composite_dates(cfg)
    until = args.until or cfg["labels"].get("dieback_until")
    if until:
        dates = [d for d in dates if d < date.fromisoformat(until)]
        print(f"Séries tronquées avant {until} : {len(dates)} composites")
    cube, ids, dates = long_table_to_cube(df, bands, dates=dates)
    print(f"Cube brut : {cube.shape[0]} pixels x {cube.shape[1]} dates x {cube.shape[2]} bandes")

    cube = scale_reflectance(cube)
    observed = np.isfinite(cube[:, :, 0]).mean()
    print(f"Observations claires : {observed:.1%} des couples pixel-date")

    series = cube_to_indices(cube, bands, names)
    ranges = cfg.get("indices_range")
    if ranges:
        avant = np.isfinite(series).sum()
        series = mask_implausible(series, names, ranges)
        ecartees = avant - np.isfinite(series).sum()
        print(f"Valeurs hors plage physique écartées : {ecartees} "
              f"({100 * ecartees / series.size:.3f} %)")
    if not args.no_interpolate:
        days = (dates - dates[0]).days.to_numpy().astype(np.float64)
        series = interpolate_gaps(series, days)
        print("Trous comblés par interpolation linéaire")

    vides = ~np.isfinite(series).any(axis=1).all(axis=1)
    if vides.any():
        print(f"{vides.sum()} pixels sans aucune observation : écartés")
        series, ids = series[~vides], ids[~vides].reset_index(drop=True)

    x, y = ids["x"].to_numpy(), ids["y"].to_numpy()
    motif = None if args.no_labels else (args.labels or cfg["labels"].get("dieback_maps"))
    cartes = sorted(str(f) for f in Path().glob(motif)) if motif else []
    if motif and not cartes:
        raise SystemExit(f"Aucune carte ne correspond à « {motif} ».")

    if cartes:
        from forest_dieback.masks import label_from_polygons
        labels, drop, onset = label_from_polygons(
            x, y, cfg["aoi"]["crs"], cartes,
            cfg["labels"].get("dieback_class_field"),
            cfg["labels"].get("dieback_positive"),
            cfg["labels"].get("dieback_excluded"),
            cfg["labels"].get("dieback_date_field"))
        print(f"{len(cartes)} cartes lues")
        if drop.any():
            print(f"{int(drop.sum())} pixels de classe ambiguë retirés du jeu")
            series, x, y = series[~drop], x[~drop], y[~drop]
            labels, onset = labels[~drop], onset[~drop]
        print(f"Étiquettes : {int(labels.sum())} pixels attaqués sur {len(labels)} "
              f"({labels.mean():.1%})")
        connues = [o for o in onset if o]
        if connues:
            print(f"Première anomalie : de {min(connues)} à {max(connues)}")
    else:
        labels = np.zeros(len(x), dtype=np.float32)
        onset = np.full(len(x), "", dtype=object)
        print("Aucune carte d'étiquettes : labels tous à 0, cube non entraînable")

    split = spatial_block_split(x, y, cfg["dataset"]["block_size_m"],
                                cfg["dataset"]["split"], cfg["dataset"]["seed"])
    print("Découpage spatial : " + ", ".join(
        f"{nom} {int((split == nom).sum())}" for nom in ("train", "val", "test")))

    out = args.out or Path(cfg["paths"]["processed"]) / "dataset.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    # split en chaînes de longueur fixe : un tableau d'objets imposerait
    # allow_pickle=True à la relecture
    np.savez_compressed(out, series=series, labels=labels, x=x, y=y,
                        split=split.astype("U5"), onset=onset.astype("U7"),
                        dates=np.array([str(d.date()) for d in dates]),
                        channels=np.array(names))
    print(f"Écrit : {out}  ({out.stat().st_size / 1e6:.1f} Mo, "
          f"{series.shape[0]} x {series.shape[1]} x {series.shape[2]})")


if __name__ == "__main__":
    main()
