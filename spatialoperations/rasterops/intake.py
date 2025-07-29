import logging
import os
from typing import Callable, Iterable, Union

import pandas as pd
import rasterio
import rioxarray as rxr
import shapely
import xarray as xr
import zarr
from odc.geo.xr import xr_zeros
from tqdm import tqdm
from typeguard import typechecked

from spatialoperations.compute import (
    ComputeItem,
    ComputeItemList,
    ComputeType,
    JoblibCompute,
    SequentialCompute,
)
from spatialoperations.config import SpatialOpsConfig
from spatialoperations.geobox import GeoboxManager
from spatialoperations.rasterops.compilers import Compilers, CompilerType
from spatialoperations.rasterops.zarr_manager import (
    ArrayListType,
    ArrayType,
    GroupType,
    ZarrManager,
    prep_array_group,
)
from spatialoperations.types.geotypes import BoundingBox, Bounds
from spatialoperations.types.indexes import Index, IndexList
from spatialoperations.types.xrtypes import RasterLike
from spatialoperations.utils.bounds_and_res import (
    conservative_regrid,
    guess_reasonable_boxbuff,
)

logger = logging.getLogger("spatialoperations._logger")

ALLOWED_EXCEPTIONS = Union[
    rxr.exceptions.NoDataInBounds,
    rxr.exceptions.OneDimensionalRaster,
    rasterio.errors.WindowError,
]

ALLOWED_EXCEPTIONS_TYPE = Iterable[ALLOWED_EXCEPTIONS]

DEFAULT_ALLOWED_EXCEPTIONS: ALLOWED_EXCEPTIONS_TYPE = (
    rxr.exceptions.NoDataInBounds,
    rxr.exceptions.OneDimensionalRaster,
    rasterio.errors.WindowError,
)


class RasterIntake:
    def __init__(self, config: SpatialOpsConfig):
        self.config = config
        self.geobox_manager = GeoboxManager(config)
        self.zarr_manager = ZarrManager(config)

    @typechecked
    def get_data_layout(self, varnames: list[str]):
        if len(varnames) > 0:
            ds = (
                xr_zeros(
                    self.geobox_manager.geobox,
                    chunks=self.config.chunk_shape,
                    dtype=self.config.dtype,
                )
                .expand_dims(
                    {
                        "var": varnames,
                    }
                )
                .rename({"longitude": "x", "latitude": "y"})
            )
            return xr.full_like(ds, self.config.nodata).to_dataset("var")

        else:
            ds = xr_zeros(
                self.geobox_manager.geobox,
                chunks=self.config.chunk_shape,
                dtype=self.config.dtype,
            ).rename({"longitude": "x", "latitude": "y"})
            return xr.full_like(ds, self.config.nodata)

    @typechecked
    def write_dataset_schema(
        self, ds: xr.Dataset, group: GroupType, overwrite_kwargs: dict = {}
    ):
        array, group = prep_array_group(
            group=group, root_group=self.zarr_manager.root_group
        )
        zarr_kwargs = {
            "mode": "a",
            "compute": False,
            "zarr_format": 3,
            "consolidated": False,
            **overwrite_kwargs,
        }
        path = os.path.join(self.config.raster_root, group.store_path.path)
        ds.to_zarr(path, **zarr_kwargs)

    @typechecked
    def get_valid_tiles_for_da(self, da: RasterLike) -> IndexList:
        raster_geobox = da.geobox
        idx_match = raster_geobox.geobox_tiles.grid_intersect(
            self.geobox_manager.geobox_tiles
        )
        return list(set([item for sublist in idx_match.values() for item in sublist]))

    @typechecked
    def get_extent_mapping_for_da(self, da: RasterLike) -> dict[Index, Bounds]:
        from shapely.geometry import MultiPolygon, box

        target_geobox = da.geobox
        try:
            mapping = target_geobox.geobox_tiles.grid_intersect(
                self.geobox_manager.geobox_tiles
            )
        except shapely.errors.GEOSException as e:
            logger.warning(
                f"{da.name} failed {e}, most likely due to the bounds mismatch"
            )
            mapping = dict()

        df = pd.DataFrame(dict(dst=mapping.keys(), src=mapping.values()))
        df = df.explode("src").groupby("src").agg(list).reset_index()

        individual_bounds = df.dst.apply(
            lambda x: target_geobox.get_bounds_for_tiles(x)
        )

        # For some reason, returning a proper Bounds object takes FOREVER
        # Probably something with the UTM CRS?
        # For now just disregarding CRS
        df["bounds"] = individual_bounds.apply(
            lambda x: Bounds(*MultiPolygon([box(*i) for i in x]).bounds, crs=None)
        )
        records = df[["src", "bounds"]].to_dict(orient="records")
        return {i["src"]: i["bounds"] for i in records}

    @typechecked
    def clip_da_to_bounds_in_native_crs(
        self, da: RasterLike, bounds: BoundingBox, expand: float | None = None
    ):
        data = da.data
        if expand is None:
            expand = guess_reasonable_boxbuff(da)

        if expand != 0:
            bounds = bounds.buffered(xbuff=expand, ybuff=expand)

        data_clipped = data.rio.clip_box(
            minx=bounds.left,
            miny=bounds.bottom,
            maxx=bounds.right,
            maxy=bounds.top,
        )
        return RasterLike(data_clipped, name=da.name)

    @typechecked
    def reproject_match_to_idx(
        self,
        da: RasterLike,
        idx: Index,
        conservative_remap: bool = False,
        nan_fix: bool = False,
        conservative_regrid_kwargs: dict = {},
        filter_gt_0: bool = False,
        reprojection_method: rasterio.enums.Resampling = rasterio.enums.Resampling.nearest,
    ) -> RasterLike:
        logger.info(f"reprojecting {da.name} to {idx}")
        data = da.data
        tile = self.geobox_manager.get_tile(idx)
        empty_da = self.geobox_manager.geobox_to_rxr(tile)
        if conservative_remap:
            logger.info(f"Conservative remapping {da.name} to {empty_da.name}")
            data = conservative_regrid(data, empty_da, **conservative_regrid_kwargs)

        else:
            data = data.rio.reproject_match(empty_da, resampling=reprojection_method)

        if nan_fix:
            data = data.where(data != data.rio.nodata, self.config.nodata)

        if filter_gt_0:
            logger.info("filtering gt0")
            data = data.where(data > 0, self.config.nodata)

        return RasterLike(data, name=da.name)

    @typechecked
    def import_raster_to_zarr(
        self,
        da: RasterLike,
        array: ArrayType,
        group: GroupType,
        idxs: IndexList = None,
        clip_in_native_crs_kwargs: dict = {},
        reproject_match_kwargs: dict = {},
        conservative_regrid_kwargs: dict = {},
        compute: ComputeType | None = SequentialCompute(),
        show_progress: bool = True,
        allowed_exceptions: ALLOWED_EXCEPTIONS_TYPE = DEFAULT_ALLOWED_EXCEPTIONS,
    ) -> tuple[Callable, ComputeItemList] | None:
        array, group = prep_array_group(
            array=array, group=group, root_group=self.zarr_manager.root_group
        )
        idxs = self.geobox_manager.get_indices(idxs)
        mapping = self.get_extent_mapping_for_da(da)
        mapping = {k: v for k, v in mapping.items() if k in idxs}

        if show_progress:
            _tqdm = tqdm
        else:
            _tqdm = lambda x: x

        _compute = compute if compute is not None else SequentialCompute()

        def create_clips(idx, bounds):
            return ComputeItem(
                args=[da, array, group, idx, bounds],
                kwargs={
                    "clip_in_native_crs_kwargs": clip_in_native_crs_kwargs,
                    "reproject_match_kwargs": reproject_match_kwargs,
                },
            )

        compute_items = _compute.execute(
            create_clips,
            [ComputeItem(args=[idx, bounds]) for idx, bounds in _tqdm(mapping.items())],
        )

        def f(
            da,
            array,
            group,
            idx,
            bounds,
            clip_in_native_crs_kwargs,
            reproject_match_kwargs,
        ):
            import warnings

            logger = logging.getLogger("spatialoperations._logger")

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Transform that is non-rectilinear or with rotation found",
                )
                try:
                    logger.info(f"Clipping {da.name} to bounds {bounds}")
                    da_clipped = self.clip_da_to_bounds_in_native_crs(
                        da, bounds, **clip_in_native_crs_kwargs
                    )
                    da_reprojected = self.reproject_match_to_idx(
                        da_clipped,
                        idx,
                        **reproject_match_kwargs,
                        conservative_regrid_kwargs=conservative_regrid_kwargs,
                    )
                    slice = self.geobox_manager.get_slice_for_idx(idx)
                    self.zarr_manager.set_data(idx, da_reprojected, array, group, slice)
                except allowed_exceptions as e:
                    logger.warning(f"Skipping {idx} due to {e} for {da.name}")

        logger.info(f"Compute items: {len(compute_items)}")
        if compute is None:
            return f, compute_items
        else:
            compute.execute(f, compute_items)

    @typechecked
    def import_multi_raster_to_zarr(
        self,
        data: dict[str, RasterLike],
        group: GroupType,
        idxs: IndexList = None,
        clip_in_native_crs_kwargs: dict = {},
        reproject_match_kwargs: dict = {},
        conservative_regrid_kwargs: dict = {},
        compute: ComputeType = SequentialCompute(),
        delayed_compute: bool = False,
        show_progress: bool = True,
    ) -> tuple[Callable, ComputeItemList] | None:
        compute_buffer = []
        for var, da in data.items():
            f, compute_items = self.import_raster_to_zarr(
                da,
                var,
                group,
                idxs=idxs,
                clip_in_native_crs_kwargs=clip_in_native_crs_kwargs,
                reproject_match_kwargs=reproject_match_kwargs,
                conservative_regrid_kwargs=conservative_regrid_kwargs,
                compute=None,
                show_progress=show_progress,
            )
            compute_buffer.extend(compute_items)

        logger.info(f"Compute buffer: {len(compute_buffer)}")
        # We're using the last `f` from the loop above
        if delayed_compute:
            return f, compute_buffer

        compute.execute(f, compute_buffer)

    @typechecked
    def import_multi_raster_to_zarr_with_prep(
        self,
        data: dict[str, RasterLike],
        group: zarr.Group | str,
        idxs: IndexList = None,
        write_dataset_schema_kwargs: dict = {},
        clip_in_native_crs_kwargs: dict = {},
        reproject_match_kwargs: dict = {},
        conservative_regrid_kwargs: dict = {},
        compute: ComputeType = SequentialCompute(),
        delayed_compute: bool = False,
        show_progress: bool = True,
        compile: bool = True,
        output_path: str | None = None,
        compile_kwargs: dict = {},
    ):
        if isinstance(group, str):
            group = self.zarr_manager.root_group[group]

        ds = self.get_data_layout(list(data.keys()))
        self.write_dataset_schema(ds, group, **write_dataset_schema_kwargs)
        compute_items = self.import_multi_raster_to_zarr(
            data,
            group,
            idxs=idxs,
            clip_in_native_crs_kwargs=clip_in_native_crs_kwargs,
            reproject_match_kwargs=reproject_match_kwargs,
            conservative_regrid_kwargs=conservative_regrid_kwargs,
            compute=compute,
            delayed_compute=delayed_compute,
            show_progress=show_progress,
        )
        if delayed_compute:
            logger.info("Delayed compute")
            f, items = compute_items
            logger.info(f"Compute items: {len(items)}")
            compute.execute(f, items)

        if compile:
            if output_path is None:
                raise ValueError("output_path must be provided if compile is True")

            paths = list(data.keys())
            self.compile_tiles(
                paths, group, output_path, idxs=idxs, compute=compute, **compile_kwargs
            )

    @typechecked
    def compile_tiles(
        self,
        arrays: ArrayListType,
        group: zarr.Group | str,
        output_path: str,
        idxs: IndexList = None,
        compiler: CompilerType = Compilers.compile_max.value,
        compute: SequentialCompute | JoblibCompute = SequentialCompute(),
        cleanup: bool = True,
    ):
        logger.info(f"Compiling tiles for {arrays}, {group}, {output_path}, {idxs}")
        arrays, group = prep_array_group(
            array=arrays, group=group, root_group=self.zarr_manager.root_group
        )
        ds = self.get_data_layout([output_path])
        self.write_dataset_schema(ds, group, overwrite_kwargs={"mode": "a"})
        idxs = self.geobox_manager.get_indices(idxs)

        if not output_path in list(group.keys()):
            ds = self.get_data_layout([output_path])
            self.write_dataset_schema(ds, group, overwrite_kwargs={"mode": "a"})

        idx_mapping = self.zarr_manager.get_idx_mapping(arrays, group, idxs)

        def f(idx, paths, group):
            geobox = self.geobox_manager.get_tile(idx)
            da = self.geobox_manager.geobox_to_rxr(geobox)
            slice = self.geobox_manager.get_slice_for_idx(idx)
            arrays = [group[path.split("/")[-1]] for path in paths]
            data = self.zarr_manager.get_data(arrays, slice)
            da.data = compiler(data)
            da = RasterLike(da)
            logger.info(f"Setting data for {idx} with {output_path}")
            self.zarr_manager.set_data(idx, da, output_path, group, slice)

        compute_items = [
            ComputeItem(args=[mapping["idx"], mapping["paths"], group])
            for mapping in idx_mapping
        ]
        compute.execute(f, compute_items)

        if cleanup:
            for array in arrays:
                del self.zarr_manager.root_group[array.name]
