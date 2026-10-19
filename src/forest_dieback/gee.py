"""Extraction des séries Sentinel-2 masquées via Google Earth Engine.

Tout est calculé côté GEE en composites médians sur une grille régulière
(10 jours par défaut), sur les seules bandes utiles aux indices, en
réflectances entières (x 10 000, uint16). Deux sorties :

- **rasters** : une pile multibande par année (bandes « AAAAMMJJ_Bx »),
  limitée au masque forestier, pour la cartographie ;
- **échantillons** : séries de pixels tirés dans le masque (ou de points
  fournis, comme les points de contrôle), en tables CSV légères, pour
  l'entraînement et les figures.

La valeur 0 signifie « pas de donnée » : hors masque, ou aucune observation
claire dans la période.
"""

from __future__ import annotations

from typing import Any

import ee

from .grid import band_names, year_periods

WORLDCOVER = "ESA/WorldCover/v200"
WORLDCOVER_TREES = 10
NODATA = 0
COVERAGE_SCALE = 100  # m ; assez fin pour une part de surface, et rapide


def init(project: str | None) -> None:
    """Initialise Earth Engine sur le projet Cloud donné."""
    if not project:
        raise ValueError("Projet GEE manquant : définir GEE_PROJECT ou gee.project")
    ee.Initialize(project=project)


def aoi_geometry(bbox: list[float]) -> ee.Geometry:
    return ee.Geometry.Rectangle(bbox, proj="EPSG:4326", geodesic=False)


def s2_collection(cfg: dict[str, Any], aoi: ee.Geometry) -> ee.ImageCollection:
    """Images S2 L2A de la zone, masquées par Cloud Score+, bandes utiles.

    ``sentinel2.tiles`` restreint aux tuiles MGRS indiquées. Les tuiles se
    recouvrent largement : une zone peut être vue par quatre d'entre elles,
    qui livrent les mêmes acquisitions. Garder celles d'une seule zone UTM
    divise d'autant le calcul et évite une reprojection à la volée des
    réflectances, qui bruiterait la série sans ajouter une seule date.
    """
    s2c = cfg["sentinel2"]
    band, threshold = s2c["cloud_score_band"], s2c["clear_threshold"]
    col = (
        ee.ImageCollection(s2c["collection"])
        .filterBounds(aoi)
        .filterDate(s2c["start_date"], s2c["end_date"])
    )
    tiles = s2c.get("tiles")
    if tiles:
        col = col.filter(ee.Filter.inList("MGRS_TILE", list(tiles)))

    def mask(img: ee.Image) -> ee.Image:
        return img.updateMask(img.select(band).gte(threshold)).select(s2c["bands"])

    return col.linkCollection(ee.ImageCollection(s2c["cloud_score"]), [band]).map(mask)


def forest_mask(cfg: dict[str, Any]) -> ee.Image:
    """Bande « mask » valant 1 sur les pixels à extraire, masquée ailleurs.

    Utilise l'asset GEE des épicéas (BD Forêt) s'il est configuré, sinon la
    classe « arbres » d'ESA WorldCover, qui inclut aussi les feuillus.
    """
    asset = cfg["extraction"].get("mask_asset")
    if asset:
        img = ee.Image(0).byte().paint(ee.FeatureCollection(asset), 1)
    else:
        img = ee.ImageCollection(WORLDCOVER).first().eq(WORLDCOVER_TREES)
    return img.selfMask().rename("mask")


def composites(col: ee.ImageCollection, periods, bands: list[str]) -> ee.ImageCollection:
    """Un composite médian par période ; masqué si la période n'a aucune image."""
    empty = ee.Image.constant([0] * len(bands)).rename(bands).updateMask(ee.Image(0))

    def composite(p):
        p = ee.List(p)
        start, end = ee.Date(p.get(0)), ee.Date(p.get(1))
        window = col.filterDate(start, end)
        img = ee.Image(ee.Algorithms.If(window.size().gt(0), window.median(), empty))
        return img.toUint16().set("system:time_start", start.millis())

    dates = ee.List([[s.isoformat(), e.isoformat()] for s, e in periods])
    return ee.ImageCollection(dates.map(composite))


def year_composites(cfg: dict[str, Any], year: int):
    """Composites d'une année et périodes correspondantes."""
    s2c = cfg["sentinel2"]
    periods = year_periods(year, s2c["composite_days"], s2c["start_date"], s2c["end_date"])
    aoi = aoi_geometry(cfg["aoi"]["bbox"])
    return composites(s2_collection(cfg, aoi), periods, s2c["bands"]), periods


def year_stack(cfg: dict[str, Any], year: int) -> tuple[ee.Image, list[str]]:
    """Pile annuelle masquée, prête à l'export, et noms de ses bandes."""
    comp, periods = year_composites(cfg, year)
    names = band_names(periods, cfg["sentinel2"]["bands"])
    stack = (
        comp.toBands()
        .rename(names)
        .updateMask(forest_mask(cfg))
        .unmask(NODATA)
        .toUint16()
    )
    return stack, names


def export_year_raster(cfg: dict[str, Any], year: int) -> tuple[ee.batch.Task, list[str]]:
    stack, names = year_stack(cfg, year)
    prefix = f"s2_{cfg['aoi']['name']}_{year}"
    task = ee.batch.Export.image.toDrive(
        image=stack,
        description=prefix,
        folder=cfg["gee"]["drive_folder"],
        fileNamePrefix=prefix,
        region=aoi_geometry(cfg["aoi"]["bbox"]),
        scale=cfg["sentinel2"]["scale"],
        crs=cfg["aoi"]["crs"],
        maxPixels=int(1e10),
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True, "noData": NODATA},
    )
    task.start()
    return task, names


def sample_points(cfg: dict[str, Any]) -> ee.FeatureCollection:
    """Pixels tirés au hasard dans le masque, avec leurs coordonnées (x, y)."""
    ex, crs = cfg["extraction"], ee.Projection(cfg["aoi"]["crs"])
    image = forest_mask(cfg).addBands(ee.Image.pixelCoordinates(crs))
    return image.stratifiedSample(
        numPoints=ex["n_samples"],
        classBand="mask",
        region=aoi_geometry(cfg["aoi"]["bbox"]),
        scale=cfg["sentinel2"]["scale"],
        projection=crs,
        seed=ex["seed"],
        tileScale=4,  # 400 km² à 10 m : découpe le calcul pour éviter les dépassements mémoire
        geometries=True,
    )


def points_from_file(path: str, crs: str, id_field: str | None = None) -> ee.FeatureCollection:
    """Points d'un fichier vecteur local (ex. points de contrôle) pour GEE.

    Chaque point garde ses coordonnées (x, y) dans ``crs`` et un identifiant
    ``pid`` (le champ ``id_field`` s'il est donné, sinon le rang).
    """
    import geopandas as gpd

    gdf = gpd.read_file(path).to_crs(crs)
    features = []
    for i, row in enumerate(gdf.itertuples()):
        x, y = float(row.geometry.x), float(row.geometry.y)
        pid = getattr(row, id_field) if id_field else i
        pid = pid.item() if hasattr(pid, "item") else pid  # numpy -> type natif
        features.append(ee.Feature(ee.Geometry.Point([x, y], crs), {"x": x, "y": y, "pid": pid}))
    return ee.FeatureCollection(features)


def series_table(cfg: dict[str, Any], year: int, points: ee.FeatureCollection,
                 properties: list[str]) -> ee.FeatureCollection:
    """Table longue : une ligne par point et par composite non masqué."""
    comp, _ = year_composites(cfg, year)
    crs, scale = ee.Projection(cfg["aoi"]["crs"]), cfg["sentinel2"]["scale"]

    def per_image(img: ee.Image) -> ee.FeatureCollection:
        day = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
        samples = img.sampleRegions(collection=points, properties=properties,
                                    scale=scale, projection=crs)
        return samples.map(lambda f: f.set("date", day))

    return ee.FeatureCollection(comp.map(per_image)).flatten()


def export_series_table(cfg: dict[str, Any], year: int, points: ee.FeatureCollection,
                        name: str, properties: list[str]) -> ee.batch.Task:
    prefix = f"{name}_{cfg['aoi']['name']}_{year}"
    task = ee.batch.Export.table.toDrive(
        collection=series_table(cfg, year, points, properties),
        description=prefix,
        folder=cfg["gee"]["drive_folder"],
        fileNamePrefix=prefix,
        fileFormat="CSV",
        selectors=[*properties, "date", *cfg["sentinel2"]["bands"]],
    )
    task.start()
    return task


def clear_fractions(cfg: dict[str, Any], year: int) -> list[float]:
    """Part de la zone masquée où chaque composite de l'année a une valeur claire.

    C'est le chiffre qui décide de la zone : une série temporelle trop trouée
    ne permet de détecter aucune rupture. Une requête GEE par année.
    """
    comp, _ = year_composites(cfg, year)
    aoi, mask = aoi_geometry(cfg["aoi"]["bbox"]), forest_mask(cfg)
    band = cfg["sentinel2"]["bands"][0]

    def fraction(img):
        return (
            ee.Image(img).select(band).mask().unmask(0).updateMask(mask)
            .reduceRegion(ee.Reducer.mean(), aoi, scale=COVERAGE_SCALE,
                          maxPixels=int(1e9), bestEffort=True)
            .get(band)
        )

    values = comp.toList(comp.size()).map(fraction).getInfo()
    return [v or 0.0 for v in values]


def describe(cfg: dict[str, Any]) -> dict[str, Any]:
    """Chiffres clés pour vérifier la zone avant de lancer les exports."""
    aoi = aoi_geometry(cfg["aoi"]["bbox"])
    n_images = s2_collection(cfg, aoi).size().getInfo()
    frac = (
        forest_mask(cfg).unmask(0)
        .reduceRegion(ee.Reducer.mean(), aoi, scale=100, maxPixels=int(1e9))
        .get("mask").getInfo()
    )
    return {"n_images": n_images, "mask_fraction": frac}
