"""Masque des épicéas à partir de la BD Forêt V2 (IGN), pour GEE et fordead.

    python scripts/prepare_spruce_mask.py data/raw/bdforet/*.shp

Télécharger la BD Forêt V2 des départements couvrant la zone (Haut-Rhin, et
vérifier Vosges et Territoire de Belfort pour la pointe ouest) sur
https://geoservices.ign.fr/bdforet, puis extraire les archives.

Dans la BD Forêt V2, épicéa et sapin forment une seule essence ; le masque
inclut donc les sapinières, moins touchées par le typographe.

Sorties : un GeoPackage (``labels.spruce_mask``) et une archive shapefile à
envoyer dans les assets GEE, dont la commande s'affiche à la fin.
"""

import argparse
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from forest_dieback.config import load_config
from forest_dieback.masks import filter_stands


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", type=Path, help="fichiers BD Forêt (shp ou gpkg)")
    p.add_argument("--config", default=None)
    p.add_argument("--field", default="ESSENCE")
    p.add_argument("--values", nargs="+", default=["Sapin, épicéa"])
    args = p.parse_args()

    cfg = load_config(args.config)
    gdf = pd.concat([gpd.read_file(f) for f in args.inputs], ignore_index=True)
    try:
        stands = filter_stands(gdf, args.field, args.values, cfg["aoi"]["bbox"])
    except KeyError as e:
        raise SystemExit(e) from e
    if stands.empty:
        values = sorted(map(str, gdf[args.field].dropna().unique()))
        raise SystemExit(f"Aucun polygone retenu. Valeurs de {args.field} : {values}")

    gpkg = Path(cfg["labels"]["spruce_mask"])
    gpkg.parent.mkdir(parents=True, exist_ok=True)
    stands.to_file(gpkg, driver="GPKG")

    shp_dir = gpkg.with_suffix("")
    shp_dir.mkdir(exist_ok=True)
    stands[[args.field, "geometry"]].to_file(shp_dir / f"{shp_dir.name}.shp")
    archive = gpkg.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w") as z:
        for f in shp_dir.iterdir():
            z.write(f, f.name)

    area = stands.to_crs(cfg["aoi"]["crs"]).area.sum() / 1e6
    print(f"{len(stands)} polygones, {area:.1f} km² -> {gpkg} et {archive}")
    project = cfg["gee"]["project"] or "<projet>"
    asset = f"projects/{project}/assets/bdforet_epicea"
    print(f"Envoi vers GEE :\n  earthengine upload table --asset_id={asset} {archive}")
    print(f"puis renseigner extraction.mask_asset: {asset} dans la configuration.")


if __name__ == "__main__":
    main()
