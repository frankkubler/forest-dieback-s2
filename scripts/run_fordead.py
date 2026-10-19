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
    bbox = cfg["aoi"]["bbox"]
    out = args.output or Path(cfg["paths"]["interim"]) / "fordead"

    fit_start, fit_end = fd.get("fit_start"), fd.get("fit_end")
    predict_start = fd.get("predict_start")
    predict_end = fd.get("predict_end") or cfg["sentinel2"]["end_date"]

    for tile in tiles:
        print(f"\n=== tuile {tile} ===")
        collection = search_items(datetime=f"{fit_start}/{predict_end}", tile=tile)
        print(f"{len(collection)} images entre {fit_start} et {predict_end}")
        if args.dry_run:
            continue

        config = FordeadConfig()
        config.fit.start, config.fit.end = fit_start, fit_end
        config.predict.start, config.predict.end = predict_start, predict_end
        if fd.get("threshold") is not None:
            config.predict.anomaly_flag_formula = f"DEVIATION > {fd['threshold']}"
        if fd.get("nmax_anomaly") is not None:
            config.predict.nmax_anomaly = fd["nmax_anomaly"]

        dest = out / tile
        dest.mkdir(parents=True, exist_ok=True)
        process = FordeadProcess(collection, output_dir=str(dest), bbox=bbox, config=config)
        print(f"Modèle harmonique sur {fit_start} à {fit_end}…", flush=True)
        process.fit()
        print(f"Surveillance de {predict_start} à {predict_end}…", flush=True)
        process.predict(timerange=(predict_start, predict_end))
        print(f"Sorties dans {dest}")


if __name__ == "__main__":
    main()
