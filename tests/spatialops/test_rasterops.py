import pytest

from spatialoperations.compute import JoblibCompute
from spatialoperations.config import SpatialOpsConfig
from spatialoperations.rasterops.export import Export
from spatialoperations.rasterops.rasterops import RasterOps
from tests.log import logger
from tests.spatialops.config import so_config
from tests.spatialops.test_fixtures import raster_intake

florida_config = SpatialOpsConfig(
    root="s3://cl-lake-test/florida-test",
    dx=0.00026977476123492776,
    epsg=4326,
    bounds=[-85.53, 23.48, -78.51, 31.7],
    chunk_size=5000,
)


@pytest.fixture(scope="session")
def rasterops():
    return RasterOps(florida_config)


@pytest.mark.s3
def test_rasterops_init(rasterops):
    assert isinstance(rasterops, RasterOps)
