import copy
import logging
import os
import shutil
import uuid
from typing import Any

import duckdb
import s3fs
from typeguard import typechecked

from spatialoperations.config import SpatialOpsConfig
from spatialoperations.types.vectortypes import VectorLike
from spatialoperations.vectorops.utils import create_connection, overwrite_parquet

logger = logging.getLogger("spatialoperations.logger")

DEFAULT_COPY_OPTIONS = {
    "FORMAT": "'PARQUET'",
    "COMPRESSION": "'ZSTD'",
    "APPEND": "TRUE",
}


class VectorIntake:
    def __init__(self, config: SpatialOpsConfig, con: duckdb.DuckDBPyConnection = None):
        self.config = config
        if con is None:
            self.con = create_connection()
        else:
            self.con = con

        if not self.config.vector_root.startswith("s3://"):
            os.makedirs(self.config.vector_root, exist_ok=True)

    @property
    def sql_envelope(self):
        return f"ST_MakeEnvelope({self.config.bounds[0]}, {self.config.bounds[1]}, {self.config.bounds[2]}, {self.config.bounds[3]})"

    @property
    def sql_filter_to_envelope(self):
        return f"WHERE ST_Intersects(geometry, {self.sql_envelope})"

    @typechecked
    def partition_dict(self, partition_by: list[str] = []) -> dict[str, str]:
        if partition_by:
            return {
                "PARTITION_BY": f"({', '.join(partition_by)})",
                "FILENAME_PATTERN": "'data_{uuid}'",
            }
        else:
            return {}

    @typechecked
    def copy_options(
        self,
        extra_copy_options: dict[str, str] = {},
        default_copy_options: dict[str, str] = DEFAULT_COPY_OPTIONS,
    ) -> dict[str, str]:
        return {**default_copy_options, **extra_copy_options}

    @typechecked
    def write_vector_to_parquet(
        self,
        data: VectorLike,
        output_name: str,
        partition_by: list[str] = [],
        overwrite: bool = False,
        filter_to_bounds: bool = True,
        append_partition_id: str | None = None,
        append_partition_column: str | None = None,
    ):
        partition_by = copy.deepcopy(partition_by)
        ddb = data.duckdb_relation
        tmp_fid = f"tmp_{str(uuid.uuid4()).split('-')[0]}"

        assert "s3://" not in output_name, (
            "Output name cannot contain s3://, as it will be appended"
        )
        parquet_path = f"{self.config.vector_root}/{output_name}"

        if not parquet_path.endswith(".parquet"):
            parquet_path = f"{parquet_path}.parquet"

        if overwrite:
            overwrite_parquet(parquet_path)

        if (append_partition_column is None) ^ (append_partition_id is None):
            raise ValueError(
                "append_partition_column must be provided if append_partition_id is provided"
            )
        if append_partition_column is not None:
            append_str = f", '{append_partition_id}' as {append_partition_column}"
            partition_by.append(append_partition_column)
        else:
            append_str = ""
        copy_options = self.copy_options(
            extra_copy_options={**self.partition_dict(partition_by)},
        )
        options_str = ", ".join(f"{k} {v}" for k, v in copy_options.items())

        sql = f"""
            COPY (
                SELECT * {append_str}
                FROM {tmp_fid}
                {self.sql_filter_to_envelope if filter_to_bounds else ""}
            )
            TO '{parquet_path}'
            ({options_str})
        """
        logger.info(f"Filtering {data.name} to envelope using {sql}")
        try:
            ddb.query(virtual_table_name=tmp_fid, sql_query=sql)
            logger.info(f"✅ Intake of {data.name} complete.")
            return parquet_path
        except Exception as e:
            logger.warning(f"❌ Intake of {data.name} failed: {e}")
            return None

    @typechecked
    def multi_write_vector_to_parquet(
        self,
        data: dict[str, VectorLike],
        output_name: str,
        overwrite: bool = False,
        append_partition_column: str | None = None,
        kwargs: dict[str, Any] = {},
    ):
        parquet_path = f"{self.config.vector_root}/{output_name}.parquet"

        if overwrite:
            overwrite_parquet(parquet_path)

        for key, value in data.items():
            logger.info(
                f"Writing {value.name} to {parquet_path} with partition id {key}"
            )
            logger.info(f"Append partition column: {append_partition_column}")
            self.write_vector_to_parquet(
                value,
                output_name,
                append_partition_id=key,
                append_partition_column=append_partition_column,
                **kwargs,
            )
