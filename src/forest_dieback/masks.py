"""Préparation du masque des peuplements d'épicéas (BD Forêt V2, IGN)."""

from __future__ import annotations

from collections.abc import Sequence

import geopandas as gpd


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
