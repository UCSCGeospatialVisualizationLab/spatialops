import pytest

from spatialoperations.compute import JoblibCompute, SequentialCompute
from spatialoperations.geobox import GeoboxManager
from spatialoperations.rasterops.intake import RasterIntake
from spatialoperations.rasterops.rasterops import RasterOps
from spatialoperations.rasterops.zarr_manager import ZarrManager
from spatialoperations.types.xrtypes import RasterLike
from tests.log import logger
from tests.spatialops.config import sample_da_str, sample_da_str2, so_config


@pytest.fixture(scope="session")
def raster_intake():
    return RasterIntake(so_config)


@pytest.fixture(scope="session")
def zarr_manager():
    return ZarrManager(so_config)


@pytest.fixture(scope="session")
def geobox_manager():
    return GeoboxManager(so_config)


@pytest.fixture(scope="session")
def test_group(raster_intake):
    return raster_intake.zarr_manager.root_group.create_group("test", overwrite=True)


@pytest.fixture(scope="session")
def write_dataset_schema(raster_intake, test_group):
    ds = raster_intake.get_data_layout(["v1", "v2"])
    raster_intake.write_dataset_schema(ds, test_group)


@pytest.fixture(scope="session")
def rasterlike_da():
    return RasterLike(sample_da_str)


@pytest.fixture(scope="session")
def multi_rasterlike_da():
    return {"v1": RasterLike(sample_da_str), "v2": RasterLike(sample_da_str2)}


@pytest.fixture(scope="session")
def seq_compute():
    return SequentialCompute()


@pytest.fixture(scope="session")
def joblib_compute():
    return JoblibCompute(n_jobs=10)


@pytest.fixture(scope="session")
def rasterops():
    return RasterOps(so_config)
