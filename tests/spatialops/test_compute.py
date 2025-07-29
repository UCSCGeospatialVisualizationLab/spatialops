import pytest
import xarray as xr

from spatialoperations.compute import ComputeItem, JoblibCompute, SequentialCompute
from tests.log import logger
from tests.spatialops.test_fixtures import (
    geobox_manager,
    joblib_compute,
    multi_rasterlike_da,
    raster_intake,
    rasterlike_da,
    rasterops,
    seq_compute,
    test_group,
    write_dataset_schema,
    zarr_manager,
)


def test_compute_init(seq_compute, joblib_compute):
    assert isinstance(seq_compute, SequentialCompute)
    assert isinstance(joblib_compute, JoblibCompute)


def simple_func(a, b, c=2):
    return a + b + c


def test_sequential_compute(seq_compute):
    items = [
        ComputeItem(args=[1, 2], kwargs={"c": 3}),
        ComputeItem(args=[4, 5], kwargs={"c": 6}),
    ]
    result = seq_compute.execute(simple_func, items)
    assert result == [6, 15]


def test_joblib_compute(joblib_compute):
    items = [
        ComputeItem(args=[1, 2], kwargs={"c": 3}),
        ComputeItem(args=[4, 5], kwargs={"c": 6}),
    ]
    result = joblib_compute.execute(simple_func, items)
    assert result == [6, 15]


@pytest.mark.s3
def test_intake_with_joblib_compute(raster_intake, joblib_compute, rasterlike_da):
    raster_intake.zarr_manager.root_group.create_group("test", overwrite=True)
    ds = raster_intake.get_data_layout(["test"])
    raster_intake.write_dataset_schema(ds, "test")
    raster_intake.import_raster_to_zarr(
        rasterlike_da, "test", "test", compute=joblib_compute
    )


@pytest.fixture(scope="session")
def intake_with_sequential_compute_multi_raster(
    raster_intake, seq_compute, multi_rasterlike_da
):
    raster_intake.zarr_manager.root_group.create_group("test", overwrite=True)
    raster_intake.import_multi_raster_to_zarr_with_prep(
        multi_rasterlike_da,
        "test",
        idxs=[(9, 10), (9, 11)],
        output_path="v1_and_v2",
        compute=seq_compute,
        delayed_compute=True,
    )


@pytest.mark.s3
def test_intake_with_sequential_compute_multi_raster(
    intake_with_sequential_compute_multi_raster, rasterops
):
    da = rasterops.get_single_xarray_tile(
        array="v1_and_v2",
        idx=(9, 10),
        group="test",
    )
    assert isinstance(da, xr.DataArray)


@pytest.mark.molokai
def test_import_multi_raster_to_zarr_with_prep_from_yaml():
    from spatialoperations.helpers import from_yaml

    from_yaml("tests/yamls/flooding_rp050.yaml")


@pytest.mark.molokai
def test_import_multi_raster_to_zarr_with_prep_from_yaml2():
    from spatialoperations.helpers import from_yaml

    from_yaml("tests/yamls/econ_inputs.yaml")
