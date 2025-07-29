# ODC imports
import logging
from typing import Iterator

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from odc.geo.geobox import GeoBox, GeoboxTiles
from odc.geo.xr import xr_zeros
from shapely.geometry import Polygon
from typeguard import typechecked

from spatialoperations.compute import ComputeType
from spatialoperations.config import BaseSpatialConfig
from spatialoperations.types.geotypes import Bounds
from spatialoperations.types.indexes import Index, IndexList
from spatialoperations.types.xrtypes import RasterLike

logger = logging.getLogger("spatialoperations.logger")


class GeoboxManager:
    def __init__(self, config: BaseSpatialConfig):
        self.config = config

    @property
    def geobox(self):
        return GeoBox.from_bbox(
            self.config.bounds, crs=self.config.epsg, resolution=self.config.dx
        )

    @property
    def geobox_tiles(self):
        return GeoboxTiles(self.geobox, self.config.chunk_shape)

    @typechecked
    def idxs_for_bounds(self, bounds: Bounds, assert_crs: bool = True) -> IndexList:
        if assert_crs:
            assert bounds.crs == self.config.epsg, (
                f"Bounds CRS must match config CRS, got {bounds.crs} and {self.config.epsg}"
            )
        return list(self.geobox_tiles.tiles(bounds.polygon))

    @typechecked
    def get_tile(self, idx: Index) -> GeoBox:
        return self.geobox_tiles[idx]

    @typechecked
    def get_indices(self, idxs: IndexList) -> IndexList:
        if idxs is None or len(idxs) == 0:
            return list(self.geobox_tiles._all_tiles())
        else:
            return idxs

    @typechecked
    def get_tiles(self, idxs: IndexList) -> list[GeoBox]:
        return [self.get_tile(idx) for idx in self.get_indices(idxs)]

    @typechecked
    def get_bounds_for_tiles(self, idxs: IndexList) -> list[Bounds]:
        idxs = self.get_indices(idxs)
        extents = []
        for tile in self.get_tiles(idxs):
            bbox = tile.boundingbox
            extents.append(
                Bounds(bbox.left, bbox.bottom, bbox.right, bbox.top, bbox.crs)
            )
        return extents

    @typechecked
    def idxs_for_raster(self, da: RasterLike):
        """Reproject a DataArray and get the tiles associated with the bounds."""
        # Get the bounds in the native CRS
        bounds = da.bounds.as_crs(self.config.epsg)
        # Get the tiles that intersect with the data array
        return self.idxs_for_bounds(bounds)

    @typechecked
    def get_covering_polygons(self, idxs: IndexList = None) -> gpd.GeoDataFrame:
        idxs = self.get_indices(idxs)
        polygons = [b.polygon for b in self.get_bounds_for_tiles(idxs)]
        x = [idx[0] for idx in idxs]
        y = [idx[1] for idx in idxs]
        return gpd.GeoDataFrame(
            pd.DataFrame({"x": x, "y": y}), geometry=polygons, crs=self.config.epsg
        )

    @typechecked
    def get_shape_for_idx(self, idx: Index) -> tuple[int, int]:
        return (self.get_tile(idx).height, self.get_tile(idx).width)

    @typechecked
    def get_slice_for_idx(self, idx: Index) -> tuple[slice, slice]:
        shape = self.get_shape_for_idx(idx)
        return (
            slice(
                idx[0] * self.config.chunk_size,
                idx[0] * self.config.chunk_size + shape[0],
            ),
            slice(
                idx[1] * self.config.chunk_size,
                idx[1] * self.config.chunk_size + shape[1],
            ),
        )

    @typechecked
    def geobox_to_rxr(self, geobox: GeoBox) -> xr.DataArray:
        # Create a dummy data array with the same shape as the Geobox
        data = np.full((geobox.height, geobox.width), self.config.nodata)
        data_array = xr.DataArray(data, dims=("y", "x"))
        data_array.rio.write_crs(self.config.epsg, inplace=True)
        data_array.rio.write_transform(geobox.transform, inplace=True)

        # Set the x and y coordinates based on the Geobox
        x_coords = (
            np.arange(geobox.width) * geobox.resolution.x
            + geobox.transform.c
            + self.config.dx / 2.0
        )
        y_coords = (
            np.arange(geobox.height) * geobox.resolution.y
            + geobox.transform.f
            - self.config.dx / 2.0
        )
        data_array = data_array.assign_coords({"x": x_coords, "y": y_coords})
        data_array = data_array.rio.set_spatial_dims(x_dim="x", y_dim="y")
        data_array.rio.write_nodata(self.config.nodata, inplace=True)
        # Create a dataset from the data array
        return data_array

    @typechecked
    def idx_mapping_for_multi_rasters(
        self, rasters: dict[str, RasterLike], compute: ComputeType
    ) -> list[dict[str, IndexList]]:
        """
        Create a mapping of tile indices to the rasters that cover them.
        """
        from spatialoperations.compute import ComputeItem

        def f(k, v):
            return k, self.idxs_for_raster(v)

        compute_items = [ComputeItem(args=(k, v)) for k, v in rasters.items()]
        to_return = {k: v for k, v in compute.execute(f, compute_items)}
        df = pd.DataFrame(to_return.items(), columns=["key", "idxs"])
        df = df.explode("idxs").groupby("idxs").agg(list).reset_index()
        df = df.rename(columns={"key": "keys", "idxs": "idx"})
        return df.to_dict(orient="records")
