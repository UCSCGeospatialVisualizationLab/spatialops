import logging
from dataclasses import dataclass

import duckdb
import s3fs
from typeguard import typechecked

from spatialoperations.config import SpatialOpsConfig
from spatialoperations.types.vectortypes import VectorLike
from spatialoperations.vectorops.intake import VectorIntake
from spatialoperations.vectorops.utils import create_connection, sql_with_retries

logger = logging.getLogger("spatialoperations._logger")


@dataclass
class ParquetFile:
    is_partitioned: bool
    path: str

    def __hash__(self):
        return hash((self.is_partitioned, self.path))


@dataclass
class ParquetView:
    view_name: str
    parquet_file: ParquetFile

    def __hash__(self):
        return hash((self.view_name, self.parquet_file))


class VectorOps:
    def __init__(
        self,
        config: SpatialOpsConfig,
        con: duckdb.DuckDBPyConnection | None = None,
        fs: s3fs.S3FileSystem | None = None,
    ):
        self.config = config
        self.intake = VectorIntake(config)
        self.con = con if con is not None else create_connection()
        self.fs = fs if fs is not None else s3fs.S3FileSystem()
        self.populate_parquet_views()

    @typechecked
    def parquet_file_to_info(self, path: str):
        """Convert a parquet file to a ParquetView."""
        is_partitioned = path.count(".parquet") > 1
        partitioned_root = path.split(".parquet")[0] + ".parquet"
        view_name = path.split("/")[-1].split(".")[0]

        return ParquetView(
            parquet_file=ParquetFile(
                is_partitioned=is_partitioned,
                path=(
                    f"s3://{partitioned_root}"
                    if "s3://" not in partitioned_root
                    else partitioned_root
                ),
            ),
            view_name=view_name,
        )

    @typechecked
    def get_parquet_info(
        self, path: str | None = None, traverse_subfolders: bool = True
    ):
        """Get all parquet files in the given path."""

        def is_partitioned(file):
            return file.count(".parquet") > 1

        def partitioned_root(file):
            return file.split(".parquet")[0] + ".parquet"

        if traverse_subfolders:
            suffix = "/**/*.parquet"
        else:
            suffix = "/*.parquet"

        if path is None:
            parquet_files = self.fs.glob(f"{self.config.vector_root}{suffix}")
        else:
            parquet_files = self.fs.glob(f"{self.config.vector_root}/{path}{suffix}")

        return list(
            set(
                [
                    ParquetView(
                        parquet_file=ParquetFile(
                            is_partitioned=is_part,
                            path=f"s3://{root_path}",
                        ),
                        view_name=root_path.split("/")[-1].split(".")[0],
                    )
                    for is_part, root_path in [
                        (is_partitioned(file), partitioned_root(file))
                        for file in parquet_files
                    ]
                ]
            )
        )

    @typechecked
    def create_view(
        self, view_name: str, path: str, is_partitioned: bool, exists_ok: bool = True
    ):
        """Create a view from a parquet file."""
        if is_partitioned:
            suffix = "/**/*.parquet"
        else:
            suffix = ""

        if exists_ok:
            exists_clause = "IF NOT EXISTS"
        else:
            exists_clause = ""

        sql = f"""
            CREATE VIEW {exists_clause} {view_name} AS
            SELECT * FROM read_parquet('{path}{suffix}');
        """
        logger.info(sql)
        sql_with_retries(self.con, sql)

    @typechecked
    def get_vectorlike(self, view_name: str):
        """Get a VectorLike object from a view."""
        sql = f"""
            SELECT * FROM {view_name};
        """
        return VectorLike(self.con.sql(sql), name=view_name)

    def populate_parquet_views(self):
        """Populate the database with the parquet files and validate CRS."""
        logger.info(f"Populating database")
        for parquet in self.get_parquet_info():
            # Create the view
            self.create_view(
                view_name=parquet.view_name,
                path=parquet.parquet_file.path,
                is_partitioned=parquet.parquet_file.is_partitioned,
            )

    @typechecked
    def get_views(self, as_list: bool = False):
        """Get all views in the database."""
        sql = """
            SELECT * EXCLUDE(sql)
            FROM duckdb_views()
            WHERE NOT internal;
        """
        results = self.con.sql(sql)
        if as_list:
            return [i[0] for i in list(results["view_name"].fetchall())]
        return results
