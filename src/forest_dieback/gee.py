"""Extraction des séries Sentinel-2 masquées via Google Earth Engine."""

from __future__ import annotations

from typing import Any

import ee


def init(project: str | None) -> None:
    """Initialise Earth Engine sur le projet Cloud donné."""
    if not project:
        raise ValueError("Projet GEE manquant : définir GEE_PROJECT ou gee.project")
    ee.Initialize(project=project)


def aoi_geometry(bbox: list[float]) -> ee.Geometry:
    return ee.Geometry.Rectangle(bbox, proj="EPSG:4326", geodesic=False)


def s2_collection(cfg: dict[str, Any], aoi: ee.Geometry) -> ee.ImageCollection:
    """Collection S2 L2A masquée par Cloud Score+, réflectances en [0, 1]."""
    s2c = cfg["sentinel2"]
    band, threshold = s2c["cloud_score_band"], s2c["clear_threshold"]
    cs = ee.ImageCollection(s2c["cloud_score"])

    def mask(img: ee.Image) -> ee.Image:
        clear = img.select(band).gte(threshold)
        return (
            img.updateMask(clear)
            .select(s2c["bands"])
            .divide(10000)
            .copyProperties(img, ["system:time_start"])
        )

    return (
        ee.ImageCollection(s2c["collection"])
        .filterBounds(aoi)
        .filterDate(s2c["start_date"], s2c["end_date"])
        .linkCollection(cs, [band])
        .map(mask)
    )


def daily_mosaics(col: ee.ImageCollection) -> ee.ImageCollection:
    """Fusionne les tuiles acquises le même jour (recouvrement d'orbites)."""
    dates = col.aggregate_array("system:time_start").map(
        lambda t: ee.Date(t).format("YYYY-MM-dd")
    ).distinct()

    def mosaic(d):
        start = ee.Date(d)
        return (
            col.filterDate(start, start.advance(1, "day"))
            .mosaic()
            .set("system:time_start", start.millis(), "date", d)
        )

    return ee.ImageCollection(dates.map(mosaic))


def export_to_drive(cfg: dict[str, Any], year: int | None = None) -> list[ee.batch.Task]:
    """Lance un export GeoTIFF par date vers Google Drive.

    Un fichier par date et par zone garde des exports légers ; ils sont
    ensuite empilés en cube xarray par ``scripts/build_cube.py``.
    """
    aoi = aoi_geometry(cfg["aoi"]["bbox"])
    col = daily_mosaics(s2_collection(cfg, aoi))
    if year is not None:
        col = col.filterDate(f"{year}-01-01", f"{year + 1}-01-01")

    tasks = []
    for d in col.aggregate_array("date").getInfo():
        img = col.filter(ee.Filter.eq("date", d)).first()
        task = ee.batch.Export.image.toDrive(
            image=img.toFloat(),
            description=f"s2_{d}",
            folder=cfg["gee"]["drive_folder"],
            fileNamePrefix=f"s2_{d}",
            region=aoi,
            scale=cfg["sentinel2"]["scale"],
            crs=cfg["aoi"]["crs"],
            maxPixels=1e10,
        )
        task.start()
        tasks.append(task)
    return tasks
