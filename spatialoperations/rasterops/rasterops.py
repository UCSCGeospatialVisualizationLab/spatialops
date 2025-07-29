import logging

import xarray as xr
from typeguard import typechecked

from spatialoperations.config import SpatialOpsConfig
from spatialoperations.geobox import GeoboxManager
from spatialoperations.rasterops.intake import RasterIntake
from spatialoperations.rasterops.zarr_manager import (
    ArrayListType,
    ArrayType,
    GroupType,
    ZarrManager,
    prep_array_group,
)
from spatialoperations.types.indexes import Index

logger = logging.getLogger("spatialoperations._logger")


class RasterOps:
    def __init__(self, config: SpatialOpsConfig):
        self.config = config
        self.geobox_manager = GeoboxManager(config)
        self.zarr_manager = ZarrManager(config)
        self.intake = RasterIntake(config)

    @typechecked
    def get_single_xarray_tile(
        self, array: ArrayType, idx: Index, group: GroupType = None
    ) -> xr.DataArray:
        array, group = prep_array_group(
            array=array, group=group, root_group=self.zarr_manager.root_group
        )
        geobox = self.geobox_manager.get_tile(idx)
        da = self.geobox_manager.geobox_to_rxr(geobox)
        slice = self.geobox_manager.get_slice_for_idx(idx)
        data = self.zarr_manager.get_data(array, slice)
        logger.info(data)
        da.data = data
        return da

    @typechecked
    def get_dataset_from_arrays(
        self, arrays: ArrayListType, idx: Index | list[Index], group: GroupType = None
    ) -> xr.Dataset:
        if not isinstance(idx, list):
            idx = [idx]

        input_array_specifiers = arrays
        if not isinstance(arrays, list):
            input_array_specifiers = [arrays]

        final_data_arrays_to_merge = []

        for i, array_specifier in enumerate(input_array_specifiers):
            # Opportunity to compute tiles
            tiles_for_this_array = [
                self.get_single_xarray_tile(array_specifier, single_idx, group)
                for single_idx in idx
            ]

            # Name all individual tile DataArrays consistently before combining.
            # get_single_xarray_tile returns an unnamed DataArray by default.
            for tile_da in tiles_for_this_array:
                if tile_da is not None:
                    tile_da.name = array_specifier

            # Filter out any None tiles that might have occurred
            valid_tiles_for_this_array = [
                td for td in tiles_for_this_array if td is not None
            ]

            if not valid_tiles_for_this_array:
                logger.warning(
                    f"No valid tiles found for array_specifier: {array_specifier} with target name {array_specifier}. Skipping."
                )
                continue

            # Combine all valid tiles for the current array_specifier.
            combined_object = xr.combine_by_coords(valid_tiles_for_this_array)

            data_array_for_final_merge: xr.DataArray
            if isinstance(combined_object, xr.DataArray):
                if combined_object.name != array_specifier:
                    combined_object.name = array_specifier
                data_array_for_final_merge = combined_object
            elif isinstance(combined_object, xr.Dataset):
                if array_specifier in combined_object.data_vars:
                    data_array_for_final_merge = combined_object[array_specifier]
                elif len(combined_object.data_vars) == 1:
                    temp_da = list(combined_object.data_vars.values())[0]
                    temp_da.name = array_specifier
                    data_array_for_final_merge = temp_da
                else:
                    raise ValueError(
                        f"xr.combine_by_coords produced an unusable Dataset for '{array_specifier}'."
                    )
            else:
                raise TypeError(
                    f"xr.combine_by_coords returned an unexpected type: {type(combined_object)} for {array_specifier}"
                )

            final_data_arrays_to_merge.append(data_array_for_final_merge)

        if not final_data_arrays_to_merge:
            logger.warning(
                "No data arrays were successfully processed to merge into a dataset."
            )
            return xr.Dataset()  # Return an empty dataset

        return xr.merge(final_data_arrays_to_merge)
