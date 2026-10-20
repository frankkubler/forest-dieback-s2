"""Étape 3 : méthode de référence FORDEAD sur la zone, par catalogue STAC.

    python scripts/run_fordead.py                      # toute la zone
    python scripts/run_fordead.py --tiles 32ULU        # une seule tuile
    python scripts/run_fordead.py --dry-run            # ne fait que compter

FORDEAD (INRAE TETIS, GPL-3) détecte les anomalies de végétation sur séries
Sentinel-2. Depuis sa version 2, il lit un catalogue STAC distant au lieu de
tuiles téléchargées : seules les fenêtres utiles de la zone transitent, pas
les tuiles entières.

La recherche d'images est ouverte, mais leur téléchargement demande un
compte sur la plateforme THEIA/MTD : au premier appel, ``teledetection``
affiche une URL et un code à autoriser dans un navigateur, puis met le jeton
en cache. Lancer ``--dry-run`` d'abord, pour vérifier l'accès sans calcul.

Deux temps, comme la méthode l'impose : un modèle harmonique ajusté sur des
années réputées saines, puis la surveillance des écarts à ce modèle. Les
dates viennent de ``fordead`` dans la configuration.

Les cartes publiées par l'INRAE (doi:10.57745/8LJGQ9) restent la référence
pour les étiquettes ; ce script sert à recalculer une référence avec les
mêmes paramètres que le modèle, pour une comparaison de méthode à méthode.
"""

import argparse
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from forest_dieback.config import load_config


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=None)
    p.add_argument("--tiles", nargs="+", default=None,
                   help="tuiles MGRS (défaut : sentinel2.tiles)")
    p.add_argument("--output", type=Path, default=None,
                   help="dossier de sortie (défaut : paths.interim/fordead)")
    p.add_argument("--dry-run", action="store_true",
                   help="compter les images disponibles, sans rien calculer")
    args = p.parse_args()

    try:
        from fordead.stac import search_items
        from fordead.workflow import FordeadConfig, FordeadProcess
    except ImportError as e:
        raise SystemExit(
            "Le package fordead n'est pas installé.\n"
            "  uv sync --all-extras        (extra « fordead », GPL-3)"
        ) from e

    cfg = load_config(args.config)
    fd = cfg.get("fordead", {})
    tiles = args.tiles or cfg["sentinel2"]["tiles"]
    # Passer la zone en géométrie plutôt qu'en bbox : une bbox est lue dans la
    # projection des images (UTM), et des degrés y désigneraient quelques mètres
    # près de l'origine. Une GeoSeries porte son CRS et se reprojette seule.
    zone = gpd.GeoSeries([box(*cfg["aoi"]["bbox"])], crs="EPSG:4326")
    # Chemin absolu : fordead réinjecte ses propres sorties dans la collection
    # STAC, et un href relatif n'y est pas résoluble — le calcul s'arrête alors
    # sur « Can not determine absolute path » après la première couche écrite.
    out = (args.output or Path(cfg["paths"]["interim"]) / "fordead").resolve()

    fit_start, fit_end = fd.get("fit_start"), fd.get("fit_end")
    predict_start = fd.get("predict_start")
    predict_end = fd.get("predict_end") or cfg["sentinel2"]["end_date"]

    for tile in tiles:
        print(f"\n=== tuile {tile} ===")
        collection = search_items(datetime=f"{fit_start}/{predict_end}", tile=tile)
        print(f"{len(collection)} images entre {fit_start} et {predict_end}")
        if args.dry_run:
            continue

        # Les deux bornes changent d'un coup : la configuration se valide à
        # chaque affectation, et poser « start » seul le comparerait à l'ancien
        # « end », qui appartient encore aux valeurs par défaut.
        config = FordeadConfig()
        config.fit = config.fit.model_copy(update={"start": fit_start, "end": fit_end})
        surveillance = {"start": predict_start, "end": predict_end}
        if fd.get("threshold") is not None:
            surveillance["anomaly_flag_formula"] = f"DEVIATION > {fd['threshold']}"
        if fd.get("nmax_anomaly") is not None:
            surveillance["nmax_anomaly"] = fd["nmax_anomaly"]
        config.predict = config.predict.model_copy(update=surveillance)
        if fd.get("write") is not None:
            # Les couches intermédiaires pèsent l'essentiel du volume écrit :
            # une liste vide ne garde que le modèle et les sorties de synthèse.
            config.write = list(fd["write"])

        dest = out / tile
        dest.mkdir(parents=True, exist_ok=True)
        assert dest.is_absolute()  # cf. la remarque sur les href plus haut
        process = FordeadProcess(collection, output_dir=str(dest),
                                 geometry=zone, config=config)
        print(f"Modèle harmonique sur {fit_start} à {fit_end}…", flush=True)
        process.fit()
        # predict() sans argument : il lit config.predict. Lui passer une
        # période désynchronise la collection, que fit() vient d'enrichir.
        print(f"Surveillance de {predict_start} à {predict_end}…", flush=True)
        process.predict()
        process.collection.save_object(str(dest / "processed_collection.json"))
        print(f"Sorties dans {dest}")


if __name__ == "__main__":
    main()
