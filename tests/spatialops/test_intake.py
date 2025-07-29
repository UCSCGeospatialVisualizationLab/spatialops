from spatialoperations.rasterops.intake import RasterIntake
from spatialoperations.rasterops.zarr_manager import ZarrManager
from spatialoperations.types.xrtypes import RasterLike
from tests.log import logger
from tests.spatialops.test_fixtures import (
    multi_rasterlike_da,
    raster_intake,
    rasterlike_da,
    test_group,
    write_dataset_schema,
    zarr_manager,
)
import pytest


@pytest.mark.s3
def test_init_raster_intake(raster_intake):
    assert isinstance(raster_intake, RasterIntake)


@pytest.mark.s3
def test_init_zarr_manager(zarr_manager):
    assert isinstance(zarr_manager, ZarrManager)


@pytest.mark.s3
def test_create_group(test_group, zarr_manager):
    assert "test" in list(zarr_manager.get_arrays_in_group(""))


@pytest.mark.s3
def test_write_dataset_schema(write_dataset_schema, raster_intake, test_group):
    assert "v1" in list(raster_intake.zarr_manager.get_arrays_in_group(test_group))


def test_rasterlike_da(rasterlike_da):
    assert isinstance(rasterlike_da, RasterLike)


def test_multi_rasterlike_da(multi_rasterlike_da):
    assert isinstance(multi_rasterlike_da, dict)
    assert isinstance(multi_rasterlike_da["v1"], RasterLike)
    assert isinstance(multi_rasterlike_da["v2"], RasterLike)


@pytest.mark.s3
def test_get_valid_tiles_for_da(raster_intake, rasterlike_da):
    tiles = raster_intake.get_valid_tiles_for_da(rasterlike_da)
    assert len(list(tiles)) > 0


@pytest.mark.s3
def test_get_extent_mapping_for_da(raster_intake, rasterlike_da):
    mapping = raster_intake.get_extent_mapping_for_da(rasterlike_da)
    assert len(mapping) > 0


@pytest.mark.s3
def test_reproject_match_to_idx(raster_intake, rasterlike_da):
    mapping = raster_intake.get_extent_mapping_for_da(rasterlike_da)
    idx = (4, 13)
    da_clipped = raster_intake.clip_da_to_bounds_in_native_crs(
        rasterlike_da, mapping[idx]
    )
    da_reprojected = raster_intake.reproject_match_to_idx(da_clipped, idx)
    assert isinstance(da_reprojected, RasterLike)
