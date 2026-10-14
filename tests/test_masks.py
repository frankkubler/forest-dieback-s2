import geopandas as gpd
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
