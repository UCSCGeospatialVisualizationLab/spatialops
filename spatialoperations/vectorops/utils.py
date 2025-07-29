import logging
import os
import shutil
import time
from urllib.parse import urlparse

import duckdb
import s3fs
from typeguard import typechecked

logger = logging.getLogger("spatialoperations.logger")


@typechecked
def authenticate_duckdb_connection(con: duckdb.DuckDBPyConnection) -> None:
    """Authenticate a DuckDB connection with necessary extensions and S3 credentials.

    Args:
        con: DuckDB connection to configure

    """
    # Install and load HTTP filesystem extension
    con.install_extension("httpfs")
    con.load_extension("httpfs")

    # Configure S3 settings
    con.execute("SET s3_url_style='path';")
    if os.getenv("AWS_ENDPOINT_URL", "").startswith("http://"):
        con.execute("SET s3_use_ssl=false;")
    con.execute(
        """
        CREATE SECRET IF NOT EXISTS secret1 (
            TYPE S3,
            KEY_ID '{}',
            SECRET '{}',
            ENDPOINT '{}'
        );
        """.format(
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
            os.getenv("AWS_ENDPOINT_URL", "")
            .replace("http://", "")
            .replace("https://", ""),
        )
    )


@typechecked
def create_connection(progress_bar: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")
    if not progress_bar:
        con.execute("SET enable_progress_bar=false")
    authenticate_duckdb_connection(con)
    return con


@typechecked
def overwrite_parquet(parquet_path: str):
    """Overwrite an existing parquet file or directory.

    This function handles both local and S3 paths.

    Args:
        parquet_path: Path to the parquet file or directory
        gd: VectorOps instance for handling S3 operations

    """
    logger.warning("overwriting the existing parquet file")
    fs = s3fs.S3FileSystem()
    if "s3://" in parquet_path:
        if fs.exists(parquet_path):
            logger.info(f"removing {parquet_path}")
            fs.rm(parquet_path, recursive=True)
    else:
        if os.path.exists(parquet_path):
            if os.path.isdir(parquet_path):
                shutil.rmtree(parquet_path)
            else:
                os.remove(parquet_path)


@typechecked
def sql_with_retries(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    retries: int = 3,
    time_between_retries: int = 4,
):
    for i in range(retries):
        try:
            res = con.sql(sql)
            if i > 1:
                logger.info(f"Success after {i} retries")
            return res
        except Exception as e:
            logger.info(e)
            logger.info(f"Retrying {i + 1} of {retries}")
            if i == retries - 1:
                raise e
            time.sleep(time_between_retries)
            continue
