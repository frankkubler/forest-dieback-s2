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
from forest_dieback.grid import split_bbox


def build_config(FordeadConfig, fd, fit_start, fit_end, predict_start, predict_end):
    """Configuration de FORDEAD d'après la section ``fordead``.

    Les bornes d'une période changent d'un seul tenant : la configuration se
    valide à chaque affectation, et poser « start » seul le comparerait à
    l'ancien « end », encore à sa valeur par défaut.
    """
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
    if fd.get("chunksize"):
        config.xarray = config.xarray.model_copy(update={"chunksize": fd["chunksize"]})
    return config


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=None)
    p.add_argument("--tiles", nargs="+", default=None,
                   help="tuiles MGRS (défaut : sentinel2.tiles)")
    p.add_argument("--output", type=Path, default=None,
                   help="dossier de sortie (défaut : paths.interim/fordead)")
    p.add_argument("--grid", type=int, default=None,
                   help="découpe la zone en n x n fenêtres (défaut : fordead.grid)")
    p.add_argument("--dry-run", action="store_true",
                   help="compter les images disponibles, sans rien calculer")
    args = p.parse_args()

    try:
        from dask.distributed import Client
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
    # Chemin absolu : fordead réinjecte ses propres sorties dans la collection
    # STAC, et un href relatif n'y est pas résoluble — le calcul s'arrête alors
    # sur « Can not determine absolute path » après la première couche écrite.
    out = (args.output or Path(cfg["paths"]["interim"]) / "fordead").resolve()

    fit_start, fit_end = fd.get("fit_start"), fd.get("fit_end")
    predict_start = fd.get("predict_start")
    predict_end = fd.get("predict_end") or cfg["sentinel2"]["end_date"]

    # L'analyse d'anomalies charge des séries temporelles entières : la mémoire
    # demandée suit la surface de la fenêtre multipliée par le nombre de dates.
    # Découper l'espace est le seul moyen de la borner, les dates portant le
    # signal qu'on cherche.
    fenetres = split_bbox(cfg["aoi"]["bbox"], int(args.grid or fd.get("grid") or 1))

    # « trimmem » et « restart_client » passent par le client dask : sans lui,
    # fordead ne les applique pas.
    client = None
    if fd.get("trimmem") or fd.get("restart_client") or fd.get("memory_limit"):
        client = Client(n_workers=int(fd.get("n_workers") or 2), threads_per_worker=2,
                        memory_limit=fd.get("memory_limit") or "auto",
                        processes=True, dashboard_address=None)
        print(f"Client dask : {len(client.scheduler_info()['workers'])} workers, "
              f"plafond {fd.get('memory_limit') or 'auto'} chacun", flush=True)

    try:
        for tile in tiles:
            print(f"\n=== tuile {tile} ===", flush=True)
            collection = search_items(datetime=f"{fit_start}/{predict_end}", tile=tile)
            print(f"{len(collection)} images entre {fit_start} et {predict_end}", flush=True)
            if args.dry_run:
                continue
            if len(fenetres) > 1:
                print(f"{len(fenetres)} fenêtres traitées l'une après l'autre", flush=True)

            for (i, j), emprise in fenetres:
                zone = gpd.GeoSeries([box(*emprise)], crs="EPSG:4326")
                dest = out / tile if len(fenetres) == 1 else out / tile / f"w{i}{j}"
                dest.mkdir(parents=True, exist_ok=True)
                assert dest.is_absolute()  # cf. la remarque sur les href plus haut
                if len(fenetres) > 1:
                    print(f"\n-- fenêtre {i},{j} --", flush=True)

                config = build_config(FordeadConfig, fd, fit_start, fit_end,
                                      predict_start, predict_end)
                process = FordeadProcess(collection, output_dir=str(dest), geometry=zone,
                                         config=config, client=client,
                                         trimmem=bool(fd.get("trimmem")),
                                         restart_client=bool(fd.get("restart_client")))
                print(f"Modèle harmonique sur {fit_start} à {fit_end}…", flush=True)
                process.fit()
                # predict() sans argument : il lit config.predict. Lui passer une
                # période désynchronise la collection, que fit() vient d'enrichir.
                print(f"Surveillance de {predict_start} à {predict_end}…", flush=True)
                process.predict()
                process.collection.save_object(str(dest / "processed_collection.json"))
                print(f"Sorties dans {dest}", flush=True)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
