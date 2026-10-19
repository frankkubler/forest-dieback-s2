import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from forest_dieback.masks import filter_stands


@pytest.fixture
def stands():
    # Polygones en Lambert-93 : deux dans la zone d'étude, un à Strasbourg
    return gpd.GeoDataFrame(
        {"ESSENCE": ["Sapin, épicéa", "Hêtre", "Sapin, épicéa"]},
        geometry=[box(1_005_000, 6_758_000, 1_006_000, 6_759_000),
                  box(1_005_000, 6_758_000, 1_006_000, 6_759_000),
                  box(1_050_000, 6_840_000, 1_051_000, 6_841_000)],
        crs=2154,
    )


def test_filter_keeps_species_inside_bbox(stands):
    out = filter_stands(stands, "ESSENCE", ["Sapin, épicéa"], [6.88, 47.75, 7.15, 47.93])
    assert len(out) == 1
    assert out.crs.to_epsg() == 4326


def test_filter_reports_missing_field(stands):
    with pytest.raises(KeyError, match="ESSENCE"):
        filter_stands(stands, "TFV", ["x"])


def _carte(tmp_path, nom, classes, centres, dates=None):
    """Petite carte de dépérissement : un disque par (classe, centre)."""
    from shapely.geometry import Point
    chemin = tmp_path / nom
    attrs = {"class": classes}
    if dates:
        attrs["Date"] = dates
    gpd.GeoDataFrame(attrs,
                     geometry=[Point(cx, cy).buffer(30) for cx, cy in centres],
                     crs="EPSG:32632").to_file(chemin, driver="GPKG")
    return str(chemin)


def test_label_from_polygons_separates_positive_and_excluded(tmp_path):
    from forest_dieback.masks import label_from_polygons

    carte = _carte(tmp_path, "c1.gpkg",
                   ["3-Forte anomalie", "4-Sol nu"],
                   [(1000, 1000), (2000, 2000)])
    x = [1000, 2000, 3000]          # attaqué, sol nu, hors zone
    y = [1000, 2000, 3000]
    labels, drop, _ = label_from_polygons(
        x, y, "EPSG:32632", [carte], "class",
        ["1-Faible anomalie", "2-Moyenne anomalie", "3-Forte anomalie"], ["4-Sol nu"])
    np.testing.assert_array_equal(labels, [1.0, 0.0, 0.0])
    np.testing.assert_array_equal(drop, [False, True, False])


def test_label_from_polygons_keeps_a_pixel_both_attacked_and_bare(tmp_path):
    """Un pixel déjà positif n'est pas retiré parce qu'il est aussi en sol nu."""
    from forest_dieback.masks import label_from_polygons

    a = _carte(tmp_path, "a.gpkg", ["3-Forte anomalie"], [(1000, 1000)])
    b = _carte(tmp_path, "b.gpkg", ["4-Sol nu"], [(1000, 1000)])
    labels, drop, _ = label_from_polygons([1000], [1000], "EPSG:32632", [a, b], "class",
                                          ["3-Forte anomalie"], ["4-Sol nu"])
    assert labels[0] == 1.0 and not drop[0]


def test_label_from_polygons_reports_an_unknown_class_field(tmp_path):
    from forest_dieback.masks import label_from_polygons

    carte = _carte(tmp_path, "c.gpkg", ["3-Forte anomalie"], [(1000, 1000)])
    with pytest.raises(KeyError, match="absent"):
        label_from_polygons([1000], [1000], "EPSG:32632", [carte], "etat", ["x"])


def test_label_from_polygons_keeps_the_earliest_onset(tmp_path):
    """Deux cartes recouvrent le pixel : la date retenue est la plus ancienne."""
    from forest_dieback.masks import label_from_polygons

    tardive = _carte(tmp_path, "t.gpkg", ["3-Forte anomalie"], [(1000, 1000)], ["2022-07"])
    precoce = _carte(tmp_path, "p.gpkg", ["3-Forte anomalie"], [(1000, 1000)], ["2019-04"])
    labels, _, onset = label_from_polygons([1000, 5000], [1000, 5000], "EPSG:32632",
                                           [tardive, precoce], "class",
                                           ["3-Forte anomalie"], date_field="Date")
    assert labels[0] == 1.0 and onset[0] == "2019-04"
    assert labels[1] == 0.0 and onset[1] == ""      # pixel sain : pas de date
