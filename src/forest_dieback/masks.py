"""Préparation du masque des peuplements d'épicéas (BD Forêt V2, IGN)."""

from __future__ import annotations

from collections.abc import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd


def filter_stands(gdf: gpd.GeoDataFrame, field: str, values: Sequence[str],
                  bbox: Sequence[float] | None = None) -> gpd.GeoDataFrame:
    """Garde les polygones dont ``field`` vaut l'une des ``values``.

    Le résultat est en WGS84 (attendu par ``earthengine upload table``) et,
    si ``bbox`` est donnée ([lon_min, lat_min, lon_max, lat_max]), limité aux
    polygones qui la touchent.
    """
    if field not in gdf.columns:
        cols = ", ".join(c for c in gdf.columns if c != "geometry")
        raise KeyError(f"Champ {field!r} absent. Colonnes disponibles : {cols}")
    out = gdf[gdf[field].isin(values)].to_crs(4326)
    if bbox is not None:
        lon0, lat0, lon1, lat1 = bbox
        out = out.cx[lon0:lon1, lat0:lat1]
    return out.reset_index(drop=True)


def label_from_polygons(x: Sequence[float], y: Sequence[float], crs: str,
                        paths: Sequence[str] | str, class_field: str | None = None,
                        positive: Sequence[str] | None = None,
                        excluded: Sequence[str] | None = None,
                        date_field: str | None = None):
    """Étiquette les points d'après des cartes de dépérissement.

    ``paths`` est une ou plusieurs couches vecteur (les cartes FORDEAD sont
    livrées par année et par région). ``class_field`` désigne l'attribut de
    classe ; ``positive`` les valeurs qui valent « attaqué » et ``excluded``
    celles dont les points sont trop ambigus pour entrer dans le jeu — le
    sol nu, par exemple, qui peut suivre une attaque comme une coupe
    ordinaire, avec une signature temporelle sans rapport.

    Renvoie ``(labels, drop, onset)`` : les étiquettes 0/1, le masque des
    points à retirer, et la date de première anomalie lue dans
    ``date_field`` (la plus ancienne quand plusieurs cartes se recouvrent,
    chaîne vide pour un point sain). Sans ``class_field``, tout polygone
    compte comme positif.

    Ce sont des **étiquettes faibles** : elles portent les erreurs de la
    méthode qui les a produites, d'où l'évaluation finale sur des points
    photo-interprétés indépendants.
    """
    if isinstance(paths, str):
        paths = [paths]
    points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), crs=crs)
    envelope = points.total_bounds  # ne lire que ce qui recouvre les points

    frames = []
    for path in paths:
        head = gpd.read_file(path, rows=1)
        bbox = gpd.GeoSeries.from_xy(
            [envelope[0], envelope[2]], [envelope[1], envelope[3]], crs=crs
        ).to_crs(head.crs).total_bounds
        layer = gpd.read_file(path, bbox=tuple(bbox))
        if len(layer):
            frames.append(layer.to_crs(crs))

    labels = np.zeros(len(points), dtype=np.float32)
    drop = np.zeros(len(points), dtype=bool)
    onset = np.full(len(points), "", dtype=object)
    if not frames:
        return labels, drop, onset

    zones = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=crs)
    if class_field is not None and class_field not in zones.columns:
        cols = ", ".join(c for c in zones.columns if c != "geometry")
        raise KeyError(f"Champ {class_field!r} absent des cartes. Disponibles : {cols}")

    def join(subset: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        if subset.empty:
            return subset.head(0)
        return gpd.sjoin(points, subset, how="inner", predicate="within")

    attaquees = zones[zones[class_field].isin(list(positive))] if (
        class_field and positive) else zones
    touche = join(attaquees)
    if len(touche):
        labels[touche.index.unique()] = 1.0
        if date_field and date_field in touche.columns:
            premiere = touche.groupby(level=0)[date_field].min()
            onset[premiere.index] = premiere.to_numpy()

    if class_field and excluded:
        ambigus = join(zones[zones[class_field].isin(list(excluded))])
        if len(ambigus):
            drop[ambigus.index.unique()] = True
            drop &= labels == 0  # un pixel déjà attaqué reste dans le jeu
    return labels, drop, onset
