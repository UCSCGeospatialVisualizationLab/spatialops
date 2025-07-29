import os

import rioxarray as rxr

from spatialoperations.config import SpatialOpsConfig
from spatialoperations.geobox import GeoboxManager
from spatialoperations.types.geotypes import Bounds
from spatialoperations.types.xrtypes import RasterLike
from tests.log import logger

test_config = {
    "root": "s3://cl-lake-test/spatialops-test",
    "dx": 0.00026977476123492776,
    "epsg": 4326,
    "bounds": [-74.754, 15.921, -67.275, 21.144],
    "chunk_size": 1000,
}

so_config = SpatialOpsConfig(**test_config)
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
sample_da = os.path.join(
    TEST_DATA_DIR,
    "rasters",
    "multiintake",
    "DOM_01_S1CC_F_20500p500_CU000_CU000_RP050_hmax.tif",
)


def test_geobox_init():
    geobox = GeoboxManager(so_config)
    print(geobox.geobox_tiles)


def test_bounds():
    da = rxr.open_rasterio(sample_da)
    bounds = Bounds.from_da(da)
    bounds.as_crs(so_config.epsg)


def test_tiles_for_bounds():
    da = RasterLike(sample_da)
    geobox = GeoboxManager(so_config)
    idxs = geobox.idxs_for_bounds(da.bounds.as_crs(so_config.epsg))
    assert len(list(idxs)) > 0


def test_get_tile():
    da = RasterLike(sample_da)
    geobox = GeoboxManager(so_config)
    idxs = geobox.idxs_for_bounds(da.bounds.as_crs(so_config.epsg))
    tile = geobox.get_tile(idxs[0])
    assert tile is not None


def test_get_tiles():
    da = RasterLike(sample_da)
    geobox = GeoboxManager(so_config)
    idxs = geobox.idxs_for_bounds(da.bounds.as_crs(so_config.epsg))
    tiles = geobox.get_tiles(idxs)
    assert len(list(tiles)) > 0


def test_get_bounds_for_tiles():
    da = RasterLike(sample_da)
    geobox = GeoboxManager(so_config)
    idxs = geobox.idxs_for_bounds(da.bounds.as_crs(so_config.epsg))
    extents = geobox.get_bounds_for_tiles(idxs)
    assert len(list(extents)) > 0


def test_get_covering_polygons():
    da = RasterLike(sample_da)
    geobox = GeoboxManager(so_config)
    idxs = geobox.idxs_for_bounds(da.bounds.as_crs(so_config.epsg))
    polygons = geobox.get_covering_polygons(idxs)
    assert len(list(polygons)) > 0


def test_rasterlike_geobox():
    da = RasterLike(sample_da)
    geobox = da.geobox
    assert geobox is not None
