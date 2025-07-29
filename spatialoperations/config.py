import os
from dataclasses import dataclass

import numpy as np
import s3fs
import zarr

from spatialoperations.types.indexes import Index


@dataclass
class BaseSpatialConfig:
    def __init__(
        self,
        epsg: int,
        bounds: tuple[float, float, float, float],
        dx: float,
        chunk_size: int,
        nodata: float = np.nan,
        dtype: str = "<f8",
    ):
        self.epsg = epsg
        self.bounds = bounds
        self.dx = dx
        self.chunk_size = chunk_size
        self.nodata = nodata
        self.dtype = dtype

    @property
    def chunk_shape(self) -> Index:
        return (self.chunk_size, self.chunk_size)


@dataclass
class SpatialOpsConfig(BaseSpatialConfig):
    def __init__(self, root: str, **kwargs):
        self.root = root
        self.raster_root = os.path.join(self.root, "raster")
        self.vector_root = os.path.join(self.root, "vector")
        # Ignore roots from kwargs
        super().__init__(**{k: v for k, v in kwargs.items() if "root" not in k})

    @property
    def get_crs(self) -> str:
        """Return the default CRS as an EPSG string.

        Returns:
            str: The default CRS in EPSG:XXXX format

        """
        return f"EPSG:{self.epsg}"


def config_from_path(path: str) -> SpatialOpsConfig:
    import json

    fs = s3fs.S3FileSystem()
    with fs.open(os.path.join(path, "config.json"), "r") as f:
        config = json.load(f)

    return SpatialOpsConfig(**config)
