"""Étape 3 : exécute la méthode de référence FORDEAD sur la zone.

FORDEAD (INRAE TETIS) est installé séparément, son environnement conda
étant lourd : https://fordead.gitlab.io/fordead_package/latest/

Ce script enchaîne les étapes standard du package. FORDEAD lit des dossiers
de tuiles Sentinel-2 au format THEIA ou Scihub (pas les GeoTIFF exportés
depuis GEE) : télécharger la ou les tuiles MGRS couvrant la zone (a priori 32ULU), puis :
  1. calcul de l'indice (CRSWIR) et masques ;
  2. ajustement du modèle harmonique sur les années « saines » ;
  3. détection des anomalies et dates de début de dépérissement ;
  4. export des résultats en raster/vecteur pour la comparaison.
"""

import argparse
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True, help="dossier des tuiles S2 (THEIA)")
    p.add_argument("--source", default="THEIA", choices=["THEIA", "Scihub", "PEPS"])
    p.add_argument("--output", type=Path, default=Path("data/interim/fordead"))
    p.add_argument("--forest-mask", type=Path, default=Path("data/raw/bdforet_epicea.gpkg"))
    p.add_argument("--min-last-date-training", default="2018-01-01")
    p.add_argument("--max-last-date-training", default="2018-06-01")
    args = p.parse_args()

    try:
        from fordead.steps.step1_compute_masked_vegetationindex import (
            compute_masked_vegetationindex,
        )
        from fordead.steps.step2_train_model import train_model
        from fordead.steps.step3_dieback_detection import dieback_detection
        from fordead.steps.step4_compute_forest_mask import compute_forest_mask
        from fordead.steps.step5_export_results import export_results
    except ImportError as e:
        raise SystemExit("Le package fordead n'est pas installé (voir la docstring).") from e

    out = str(args.output)
    compute_masked_vegetationindex(input_directory=str(args.input), data_directory=out,
                                   sentinel_source=args.source, vi="CRSWIR",
                                   apply_source_mask=True)
    train_model(data_directory=out,
                min_last_date_training=args.min_last_date_training,
                max_last_date_training=args.max_last_date_training)
    dieback_detection(data_directory=out)
    compute_forest_mask(data_directory=out, forest_mask_source="vector",
                        vector_path=str(args.forest_mask))
    export_results(data_directory=out, frequency="M", multiple_files=False)
    print(f"Résultats FORDEAD dans {out}")


if __name__ == "__main__":
    main()
