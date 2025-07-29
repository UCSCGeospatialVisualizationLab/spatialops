import logging
from glob import glob

import numpy as np
import pandas as pd
import s3fs
import zarr
from typeguard import typechecked

from spatialoperations.config import SpatialOpsConfig
from spatialoperations.types.indexes import Index, IndexList
from spatialoperations.types.xrtypes import RasterLike

logger = logging.getLogger("spatialoperations._logger")


ArrayType = zarr.Array | str | None
GroupType = zarr.Group | str | None
ArrayListType = list[ArrayType] | ArrayType


def prep_array_group(
    array: ArrayListType = None, group: GroupType = None, root_group: zarr.Group = None
) -> tuple[ArrayListType, GroupType]:
    if isinstance(group, str):
        group = root_group[group]
    if isinstance(array, str):
        array = group[array]
    elif isinstance(array, list):
        array = [group[a] if isinstance(a, str) else a for a in array]
    return array, group


class ZarrManager:
    def __init__(self, config: SpatialOpsConfig):
        self.config = config
        self.fs = s3fs.S3FileSystem()
        self.storage = zarr.open_group(store=self.config.raster_root, mode="a")

    @property
    def root_group(self) -> zarr.Group:
        return self.storage

    @typechecked
    def get_arrays_in_group(self, group: GroupType) -> ArrayListType:
        array, group = prep_array_group(group=group, root_group=self.root_group)
        vars_to_ignore = ["spatial_ref", "x", "y"]
        return [i for i in list(group) if i not in vars_to_ignore]

    @typechecked
    def set_data(
        self,
        idx: Index,
        da: RasterLike,
        array: ArrayType,
        group: GroupType,
        slice: tuple[slice, slice],
    ):
        array, group = prep_array_group(
            array=array, group=group, root_group=self.root_group
        )
        logger.info(f"Setting data for {idx} with {array}")
        data = da.data
        if data.y[0] < data.y[-1]:
            data = data.reindex(y=data.y[::-1])

        array[slice] = data.astype("float32")
        return idx

    @typechecked
    def get_data(self, array: ArrayListType, slice: tuple[slice, slice]) -> np.ndarray:
        if isinstance(array, list):
            return np.array([i[slice] for i in array])
        else:
            data = array[slice]
            # Pulling uninitialized data out of the Zarr returns all 0s
            # So I'm hacking this to return the nodata value instead
            if np.max(data) == 0 and np.min(data) == 0:
                return np.full_like(data, self.config.nodata)
            return data

    @typechecked
    def chunks_initialized(self, array: ArrayType, group: GroupType) -> IndexList:
        array, group = prep_array_group(
            array=array, group=group, root_group=self.root_group
        )
        root = f"{self.config.raster_root}{array.name}/c"
        root_no_s3 = root.replace("s3://", "")
        if root.startswith("s3://"):
            all_paths = self.fs.glob(f"{root}/**/*")
        else:
            all_paths = glob(f"{root}/**/*")
        suffixes = [p.replace(f"{root_no_s3}/", "") for p in all_paths]
        chunks = [
            tuple(int(x) for x in p.split("/"))
            for p in suffixes
            if len(p.split("/")) == 2
        ]
        return chunks

    @typechecked
    def multi_chunks_initialized(
        self,
        data: list[tuple[ArrayType, GroupType]],
    ) -> IndexList:
        all_data = [self.chunks_initialized(array, group) for array, group in data]
        return list(
            set([chunk for sublist in all_data if sublist for chunk in sublist])
        )

    @typechecked
    def get_idx_mapping(
        self,
        arrays: ArrayListType,
        group: GroupType,
        idxs: IndexList = None,
    ) -> list[dict[ArrayType, IndexList]]:
        if not isinstance(arrays, list):
            arrays = [arrays]
        arrays, group = prep_array_group(
            array=arrays, group=group, root_group=self.root_group
        )
        paths = [array.name.split("/")[-1] for array in arrays]

        paths_df = pd.DataFrame(paths, columns=["path"])
        paths_df["idx"] = paths_df.apply(
            lambda row: self.chunks_initialized(row["path"], group), axis=1
        )
        paths_df = paths_df.explode("idx")
        if idxs is not None:
            paths_df = paths_df[paths_df["idx"].isin(idxs)]
        paths_df = (
            paths_df.groupby("idx")
            .agg(list)
            .reset_index()
            .rename(columns={"path": "paths"})
        )
        logger.info(f"Paths df: {paths_df}")
        return paths_df.to_dict(orient="records")
