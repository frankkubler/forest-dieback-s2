"""Étape 1 : lance les exports GEE des séries Sentinel-2 masquées vers Drive.

    python scripts/extract_s2.py --year 2023
"""

import argparse

from forest_dieback import gee
from forest_dieback.config import load_config


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=None)
    p.add_argument("--year", type=int, default=None, help="limiter à une année")
    p.add_argument("--dry-run", action="store_true", help="compter les dates sans exporter")
    args = p.parse_args()

    cfg = load_config(args.config)
    gee.init(cfg["gee"]["project"])
    if args.dry_run:
        aoi = gee.aoi_geometry(cfg["aoi"]["bbox"])
        col = gee.daily_mosaics(gee.s2_collection(cfg, aoi))
        print(f"{col.size().getInfo()} dates disponibles sur la zone")
        return
    tasks = gee.export_to_drive(cfg, args.year)
    print(f"{len(tasks)} exports lancés vers Drive/{cfg['gee']['drive_folder']}")


if __name__ == "__main__":
    main()
