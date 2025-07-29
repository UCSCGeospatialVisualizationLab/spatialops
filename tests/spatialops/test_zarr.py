import logging

import numpy as np
import pytest

from spatialoperations.geobox import GeoboxManager
from spatialoperations.rasterops.compilers import Compilers
from spatialoperations.rasterops.zarr_manager import ZarrManager
from tests.log import logger
from tests.spatialops.test_fixtures import (
    geobox_manager,
    multi_rasterlike_da,
    raster_intake,
    seq_compute,
    zarr_manager,
)


@pytest.fixture(scope="session")
def intake_for_zarr_tests(raster_intake, seq_compute, multi_rasterlike_da):
    raster_intake.zarr_manager.root_group.create_group("test2", overwrite=True)
    raster_intake.import_multi_raster_to_zarr_with_prep(
        multi_rasterlike_da,
        "test2",
        idxs=[(9, 10), (9, 11)],
        output_path="v1_and_v2",
        compute=seq_compute,
        delayed_compute=True,
        compile_kwargs={"cleanup": False},
    )


@pytest.mark.s3
def test_intake_for_zarr_tests(intake_for_zarr_tests, zarr_manager):
    assert "v1_and_v2" in list(zarr_manager.root_group["test2"].keys())


@pytest.mark.s3
def test_chunks_initialized(intake_for_zarr_tests, zarr_manager):
    chunks = zarr_manager.chunks_initialized(array="v1", group="test2")
    assert len(chunks) > 0
    chunks2 = zarr_manager.chunks_initialized(array="v2", group="test2")
    assert len(chunks2) > 0
    chunks3 = zarr_manager.chunks_initialized(array="v1_and_v2", group="test2")
    assert len(chunks3) > 0


@pytest.mark.s3
def test_get_arrays_in_group(intake_for_zarr_tests, zarr_manager):
    arrays = zarr_manager.get_arrays_in_group(group="test2")
    assert len(arrays) > 0


@pytest.mark.s3
def test_get_idx_mapping(intake_for_zarr_tests, zarr_manager):
    group = "test2"
    arrays = zarr_manager.get_arrays_in_group(group)
    mapping = zarr_manager.get_idx_mapping(arrays, group)
    assert len(mapping) > 0


@pytest.mark.s3
def test_get_data_multiple(intake_for_zarr_tests, zarr_manager, geobox_manager):
    idx = (9, 10)
    slice = geobox_manager.get_slice_for_idx(idx)
    group = "test2"
    arrays = [zarr_manager.root_group[group][d] for d in ["v1", "v2"]]
    data = zarr_manager.get_data(arrays, slice)
    assert np.nanmax(data) > 0


@pytest.mark.s3
def test_compile_first(intake_for_zarr_tests, zarr_manager, geobox_manager):
    idx = (9, 10)
    slice = geobox_manager.get_slice_for_idx(idx)
    group = "test2"
    arrays = [zarr_manager.root_group[group][d] for d in ["v1", "v2"]]
    data = zarr_manager.get_data(arrays, slice)
    logger.info(f"idx: {idx}, data.max(): {np.nanmax(data)}")
    compiled = Compilers.compile_max.value(data)
    logger.info(f"compiled: {compiled}")
    assert np.nanmax(compiled) > 0
