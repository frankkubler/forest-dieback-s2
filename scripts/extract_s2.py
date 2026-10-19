"""Étape 1 : extraction GEE des composites Sentinel-2 masqués.

    python scripts/extract_s2.py check                 # chiffres clés, aucun export
    python scripts/extract_s2.py check --coverage --years 2022   # trous de la série
    python scripts/extract_s2.py samples               # séries de pixels tirés (CSV)
    python scripts/extract_s2.py points --file data/raw/control_points.gpkg
    python scripts/extract_s2.py rasters --years 2022 2023

Les exports partent vers Google Drive (dossier ``gee.drive_folder``), une
tâche par année ; leur avancement se suit dans l'onglet Tasks du Code Editor
ou avec ``earthengine --project=<projet> task list`` — sans ``--project`` ni
``GEE_PROJECT``, la commande s'arrête sur « no project found ».
"""

import argparse
import json
from pathlib import Path

from forest_dieback import gee
from forest_dieback.config import load_config
from forest_dieback.grid import (
    bbox_shape,
    coverage_summary,
    estimate_bytes,
    year_periods,
    years_in_range,
)


def selected_years(cfg, years):
    s2c = cfg["sentinel2"]
    available = years_in_range(s2c["start_date"], s2c["end_date"])
    if not years:
        return available
    unknown = sorted(set(years) - set(available))
    if unknown:
        raise SystemExit(f"Années hors de la période configurée : {unknown}")
    return years


def cmd_check(cfg, args):
    s2c, ex = cfg["sentinel2"], cfg["extraction"]
    cols, rows = bbox_shape(cfg["aoi"]["bbox"], s2c["scale"])
    info = gee.describe(cfg)
    mask = ex.get("mask_asset") or "ESA WorldCover (arbres)"
    print(f"Zone {cfg['aoi']['name']} : {cols} x {rows} pixels à {s2c['scale']} m")
    print(f"Masque : {mask}, {info['mask_fraction']:.0%} de la zone")
    print(f"Images S2 sur la période : {info['n_images']}")
    total, n_periods = 0, 0
    for year in selected_years(cfg, args.years):
        n = len(year_periods(year, s2c["composite_days"], s2c["start_date"], s2c["end_date"]))
        size = estimate_bytes(cols * rows, n, len(s2c["bands"]))
        total, n_periods = total + size, n_periods + n
        print(f"  {year} : {n} composites, pile brute {size / 1e9:.1f} Go "
              f"dont {info['mask_fraction']:.0%} dans le masque")
    print(f"Total brut des rasters : {total / 1e9:.1f} Go avant compression "
          f"(vérifier la taille réelle sur une première année)")
    n_rows = ex["n_samples"] * n_periods
    print(f"Échantillons : {ex['n_samples']} pixels, au plus {n_rows} lignes CSV "
          f"(~{n_rows * 60 / 1e6:.0f} Mo)")
    if args.coverage:
        print("Part de la zone masquée où le composite est clair "
              "(une requête GEE par année) :")
        for year in selected_years(cfg, args.years):
            periods = year_periods(year, s2c["composite_days"],
                                   s2c["start_date"], s2c["end_date"])
            c = coverage_summary(periods, gee.clear_fractions(cfg, year))
            print(f"  {year} : moyenne {c['mean']:.0%}, "
                  f"avril-septembre {c['season_mean']:.0%} sur {c['n_season']} composites, "
                  f"{c['n_poor']}/{c['n_total']} composites sous 50 %")


def cmd_rasters(cfg, args):
    out = Path(cfg["paths"]["raw"]) / "s2"
    out.mkdir(parents=True, exist_ok=True)
    for year in selected_years(cfg, args.years):
        task, names = gee.export_year_raster(cfg, year)
        meta = {"bands": names, "nodata": gee.NODATA, "scale_factor": 1e-4,
                "crs": cfg["aoi"]["crs"], "resolution_m": cfg["sentinel2"]["scale"]}
        meta_path = out / f"s2_{cfg['aoi']['name']}_{year}_bands.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"{year} : tâche {task.id} lancée, ordre des bandes dans {meta_path}")


def cmd_samples(cfg, args):
    if args.n:
        cfg["extraction"]["n_samples"] = args.n
    points = gee.sample_points(cfg)
    for year in selected_years(cfg, args.years):
        task = gee.export_series_table(cfg, year, points, "samples", ["x", "y"])
        print(f"{year} : tâche {task.id} lancée")


def cmd_points(cfg, args):
    points = gee.points_from_file(str(args.file), cfg["aoi"]["crs"], args.id_field)
    for year in selected_years(cfg, args.years):
        task = gee.export_series_table(cfg, year, points, args.name, ["pid", "x", "y"])
        print(f"{year} : tâche {task.id} lancée")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, func, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--years", type=int, nargs="+", help="par défaut : toute la période")
        sp.set_defaults(func=func)
        return sp

    add("check", cmd_check, "chiffres clés de la zone, sans export").add_argument(
        "--coverage", action="store_true",
        help="mesurer la part de pixels clairs par composite (lent)")
    add("rasters", cmd_rasters, "piles annuelles de composites (GeoTIFF)")
    add("samples", cmd_samples, "séries de pixels tirés dans le masque (CSV)").add_argument(
        "--n", type=int, help="nombre de pixels (défaut : extraction.n_samples)")
    sp = add("points", cmd_points, "séries aux points d'un fichier vecteur (CSV)")
    sp.add_argument("--file", type=Path, required=True)
    sp.add_argument("--id-field", default=None, help="champ identifiant (défaut : rang)")
    sp.add_argument("--name", default="points", help="préfixe des fichiers exportés")

    args = p.parse_args()
    cfg = load_config(args.config)
    gee.init(cfg["gee"]["project"])
    args.func(cfg, args)


if __name__ == "__main__":
    main()
