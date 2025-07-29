import os
from dataclasses import dataclass
from typing import Union

import rioxarray as rxr
import xarray as xr
from typeguard import typechecked

from spatialoperations.config import BaseSpatialConfig
from spatialoperations.types.geotypes import Bounds

DataArrayLike = Union[str, xr.DataArray]


@dataclass
class RasterLike:
    """A RasterLike is a DataArray or a path to a DataArray."""

    _data: DataArrayLike
    name: str | None = None

    @typechecked
    def __init__(self, da: DataArrayLike, name: str | None = None):
        self._data = da
        if isinstance(da, str) and name is None:
            self.name = da
        else:
            self.name = name

    @property
    def data(self):
        if isinstance(self._data, str):
            return rxr.open_rasterio(self._data).isel(band=0)
        else:
            return self._data

    @property
    def crs(self):
        return self.data.odc.crs

    @property
    def bounds(self):
        return Bounds.from_da(self.data)

    @property
    def geobox(self, chunk_size: int = 1000):
        from spatialoperations.geobox import GeoboxManager

        res = abs(self.data.rio.resolution()[0])
        config = BaseSpatialConfig(
            epsg=self.crs,
            bounds=self.bounds,
            dx=res,
            chunk_size=chunk_size,
        )
        return GeoboxManager(config)
