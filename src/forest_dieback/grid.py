"""Grilles temporelle et spatiale de l'extraction (pur Python, testable sans GEE)."""

from __future__ import annotations

import math
from datetime import date, timedelta


def parse_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def years_in_range(start: str | date, end: str | date) -> list[int]:
    """Années couvertes par l'intervalle [start, end)."""
    start, end = parse_date(start), parse_date(end)
    last = (end - timedelta(days=1)).year
    return list(range(start.year, last + 1))


def year_periods(year: int, step_days: int, start: str | date | None = None,
                 end: str | date | None = None) -> list[tuple[date, date]]:
    """Périodes [début, fin) de ``step_days`` jours, alignées sur le 1er janvier.

    La dernière période de l'année s'arrête au 1er janvier suivant, pour que
    chaque année s'exporte indépendamment. Les périodes sont rognées à
    [start, end) ; celles qui tombent entièrement dehors sont écartées.
    """
    y0, y1 = date(year, 1, 1), date(year + 1, 1, 1)
    lo = max(y0, parse_date(start)) if start else y0
    hi = min(y1, parse_date(end)) if end else y1
    periods = []
    d = y0
    while d < y1:
        e = min(d + timedelta(days=step_days), y1)
        s_, e_ = max(d, lo), min(e, hi)
        if s_ < e_:
            periods.append((s_, e_))
        d = e
    return periods


def band_names(periods: list[tuple[date, date]], bands: list[str]) -> list[str]:
    """Noms des bandes d'une pile annuelle, dans l'ordre de ``toBands()``."""
    return [f"{s:%Y%m%d}_{b}" for s, _ in periods for b in bands]


def bbox_shape(bbox: list[float], scale: float) -> tuple[int, int]:
    """Taille approximative (colonnes, lignes) d'une emprise WGS84 à ``scale`` m."""
    lon0, lat0, lon1, lat1 = bbox
    lat_mid = math.radians((lat0 + lat1) / 2)
    width = (lon1 - lon0) * 111_320 * math.cos(lat_mid)
    height = (lat1 - lat0) * 111_320
    return round(width / scale), round(height / scale)


def estimate_bytes(n_pixels: int, n_periods: int, n_bands: int,
                   bytes_per_value: int = 2) -> int:
    """Volume brut (non compressé) d'une pile de composites."""
    return n_pixels * n_periods * n_bands * bytes_per_value


def coverage_summary(periods: list[tuple[date, date]], fractions: list[float],
                     season: tuple[int, int] = (4, 9),
                     threshold: float = 0.5) -> dict[str, float]:
    """Résumé des parts de pixels clairs d'une année de composites.

    ``season`` borne les mois où le dépérissement se lit le mieux (feuillaison
    complète) ; ``threshold`` marque les composites trop troués pour servir.
    """
    if not fractions:
        return {"mean": 0.0, "season_mean": 0.0, "n_season": 0, "n_poor": 0, "n_total": 0}
    pairs = zip(periods, fractions, strict=True)  # une fraction par composite, sinon c'est un bug
    in_season = [f for (s_, _), f in pairs if season[0] <= s_.month <= season[1]]
    return {
        "mean": sum(fractions) / len(fractions),
        "season_mean": sum(in_season) / len(in_season) if in_season else 0.0,
        "n_season": len(in_season),
        "n_poor": sum(f < threshold for f in fractions),
        "n_total": len(fractions),
    }


def split_bbox(bbox: list[float], n: int) -> list[tuple[tuple[int, int], list[float]]]:
    """Découpe une emprise en une grille de n x n sous-fenêtres.

    Chaque fenêtre est rendue avec ses indices (colonne, ligne) et sa propre
    emprise, dans l'unité de ``bbox``. ``n = 1`` rend l'emprise entière.

    Le découpage existe pour la mémoire : une analyse qui charge la série
    temporelle complète d'une zone demande une place proportionnelle à sa
    surface, que le nombre de dates multiplie.
    """
    if n < 1:
        raise ValueError(f"Grille de {n} x {n} : il en faut au moins une.")
    lon0, lat0, lon1, lat1 = bbox
    dlon, dlat = (lon1 - lon0) / n, (lat1 - lat0) / n
    return [
        ((i, j), [lon0 + i * dlon, lat0 + j * dlat,
                  lon0 + (i + 1) * dlon, lat0 + (j + 1) * dlat])
        for i in range(n)
        for j in range(n)
    ]
