import os

import rioxarray as rxr
import xarray as xr

from spatialoperations.types.geotypes import Bounds
from spatialoperations.types.xrtypes import RasterLike

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
sample_da_str = os.path.join(
    TEST_DATA_DIR,
    "rasters",
    "multiintake",
    "DOM_01_S1CC_F_20500p500_CU000_CU000_RP050_hmax.tif",
)
sample_da = rxr.open_rasterio(sample_da_str).isel(band=0)


def test_rasterlike():
    da = RasterLike(sample_da)
    assert isinstance(da.data, xr.DataArray)

    da_str = RasterLike(sample_da_str)
    assert isinstance(da_str.data, xr.DataArray)

    bounds = da_str.bounds
    assert isinstance(bounds, Bounds)
