import json
import logging as std_logging
import os
import warnings

import s3fs

from spatialoperations.config import SpatialOpsConfig, config_from_path
from spatialoperations.logging import logger
from spatialoperations.rasterops.rasterops import RasterOps
from spatialoperations.vectorops.vectorops import VectorOps

warnings.filterwarnings("ignore", message="Found credentials in environment variables.")
warnings.filterwarnings(
    "ignore", message="Found endpoint for s3 via: environment_global."
)


class SpatialOperations:
    def __init__(
        self,
        config: SpatialOpsConfig | None = None,
        path: str | None = None,
        overwrite: bool = False,
        logger: std_logging.Logger = logger,
    ):
        self.logger = logger
        if not ((config is None) ^ (path is None)):
            raise ValueError("Either config or path must be provided, not both")

        logging.getLogger("botocore.credentials").setLevel(logging.WARNING)
        self.fs = s3fs.S3FileSystem()

        if path is not None:
            self.config = config_from_path(path)
        else:
            self.config = config

        if overwrite:
            # Check if the root path exists before attempting to delete it
            if self.fs.exists(self.config.root):
                self.logger.info(f"Removing existing data at {self.config.root}")
                self.fs.rm(self.config.root, recursive=True)
            else:
                self.logger.info(f"Creating new data store at {self.config.root}")

        self.ro = RasterOps(self.config)
        self.vo = VectorOps(self.config, fs=self.fs)

        # Create config.json path
        config_path = os.path.join(self.config.root, "config.json")

        if path is not None:
            logger.info(f"Writing config to {config_path}")
            logger.info(self.config.__dict__)
        # Write config to file
        with self.fs.open(config_path, "w") as f:
            json.dump(self.config.__dict__, f, indent=2)
