"""Préparation du masque des peuplements d'épicéas (BD Forêt V2, IGN)."""

from __future__ import annotations

from collections.abc import Sequence

import geopandas as gpd
import numpy as np


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
                        path: str, year_field: str | None = None,
                        years: Sequence[int] | None = None) -> np.ndarray:
    """Étiquette 1 les points tombant dans un polygone de dépérissement, 0 sinon.

    ``path`` est une couche vecteur des zones détectées (cartes FORDEAD
    publiées, ou export d'un passage local). ``year_field`` et ``years``
    restreignent aux polygones d'une période, quand la couche porte l'année
    de détection ; sans eux, tous les polygones comptent.

    Ce sont des **étiquettes faibles** : elles reprennent les erreurs de la
    méthode qui les a produites. L'évaluation finale s'appuie sur les points
    photo-interprétés, indépendants.
    """
    zones = gpd.read_file(path)
    if year_field is not None and years is not None:
        zones = zones[zones[year_field].isin(list(years))]
    points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), crs=crs)
    zones = zones.to_crs(crs)
    hit = gpd.sjoin(points, zones[["geometry"]], how="left", predicate="within")
    hit = hit[~hit.index.duplicated(keep="first")]  # un point dans 2 polygones reste 1
    return hit["index_right"].notna().to_numpy().astype(np.float32)
