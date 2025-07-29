import logging
import tempfile
import uuid
from dataclasses import dataclass
from typing import Union

import duckdb
import geopandas as gpd
from typeguard import typechecked

from spatialoperations.vectorops.pmtiles import TileOpts

VectorData = Union[str, duckdb.DuckDBPyRelation, gpd.GeoDataFrame]

logger = logging.getLogger("spatialoperations._logger")


@dataclass
class VectorLike:
    @typechecked
    def __init__(
        self,
        data: VectorData,
        name: str | None = None,
        layer: str | None = None,
        crs: str | None = None,
        con: duckdb.DuckDBPyConnection | None = None,
    ):
        self._data = data
        if name is None:
            if isinstance(data, str):
                self.name = data
            else:
                self.name = None
        else:
            self.name = name
        self.layer = layer
        self.crs = crs
        self._con = con

        if isinstance(data, str):
            self.path = data
        else:
            self.path = None

    @property
    def con(self):
        if self._con is None:
            raise ValueError("Connection is required for string data")
        return self._con

    @con.setter
    @typechecked
    def con(self, con: duckdb.DuckDBPyConnection):
        self._con = con

    @property
    def columns(self):
        if isinstance(self._data, str):
            if self.con is None:
                raise ValueError("Connection is required for string data")
            return (
                self.con.sql(f"SELECT * FROM {self.from_clause} LIMIT 0")
                .df()
                .columns.tolist()
            )
        elif isinstance(self._data, duckdb.DuckDBPyRelation):
            return (
                self._data.query(
                    virtual_table_name="tmp_view_name",
                    sql_query=f"SELECT * FROM tmp_view_name LIMIT 0",
                )
                .df()
                .columns.tolist()
            )
        else:
            return self._data.columns

    @property
    def from_clause(self):
        if isinstance(self._data, str):
            layer_str = f', layer="{self.layer}"' if self.layer else ""
            return f"st_read('{self._data}'{layer_str})"
        else:
            raise ValueError(f"Data must be a string, got {type(self._data)}")

    @typechecked
    def get_reprojected(self, crs: str, source_crs: str | None = None) -> VectorData:
        if isinstance(self._data, str):
            return self.ogr_to_gdf().to_crs(crs)
        elif isinstance(self._data, duckdb.DuckDBPyRelation):
            fid = f"tmp_{str(uuid.uuid4()).split('-')[0]}"
            v = self.duckdb_relation

            if not source_crs:
                raise ValueError("Source CRS is required for reprojecting from DuckDB")

            if not source_crs.startswith("EPSG:"):
                source_crs = f"EPSG:{source_crs}"
            if not crs.startswith("EPSG:"):
                crs = f"EPSG:{crs}"

            sql = f"SELECT * EXCLUDE ({self.geom_column}), ST_Transform({self.geom_column}, '{source_crs}', '{crs}') as geometry FROM {fid}"
            logger.info(f"Reprojecting from {source_crs} to {crs} using {sql}")
            return v.query(virtual_table_name=fid, sql_query=sql)
        else:
            return self._data.to_crs(crs)

    @property
    def geom_column(self):
        columns = self.columns
        if "geometry" in columns:
            if "geom" in columns:
                raise ValueError(
                    "Both 'geometry' and 'geom' columns found in source data"
                )
            return "geometry"
        elif "geom" in columns:
            return "geom"
        else:
            raise ValueError("No geometry column found in source data")

    @typechecked
    def ogr_to_duckdb(self, con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyRelation:
        assert isinstance(self._data, str), (
            f"Data must be a string, got {type(self._data)}"
        )
        print(f"Reading {self._data} to DuckDB")
        sql = f"SELECT * EXCLUDE({self.geom_column}), {self.geom_column} as geometry FROM {self.from_clause}"
        print(f"Executing {sql}")
        return con.sql(sql)

    @typechecked
    def duckdb_to_gdf(self) -> gpd.GeoDataFrame:
        assert isinstance(self._data, duckdb.DuckDBPyRelation), (
            f"Data must be a DuckDB relation, got {type(self._data)}"
        )
        tmp_view_name = "tmp_table"
        sql = (
            f"SELECT * EXCLUDE ({self.geom_column}), "
            f"ST_AsText({self.geom_column}) as geometry_wkt "
            f"FROM {tmp_view_name}"
        )

        df = self._data.query(virtual_table_name=tmp_view_name, sql_query=sql).df()
        df["geometry"] = gpd.GeoSeries.from_wkt(df["geometry_wkt"])
        df.drop(columns=["geometry_wkt"], inplace=True)
        return gpd.GeoDataFrame(df, geometry="geometry", crs=self.crs)

    @typechecked
    def duckdb_to_flatgeobuf(self, path: str | None = None) -> str:
        assert isinstance(self._data, duckdb.DuckDBPyRelation), (
            f"Data must be a DuckDB relation, got {type(self._data)}"
        )
        if path is None:
            path = tempfile.NamedTemporaryFile(suffix=".fgb").name

        fid = f"tmp_{str(uuid.uuid4()).split('-')[0]}"
        self._data.query(
            virtual_table_name=fid,
            sql_query=f"COPY (SELECT * FROM {fid}) TO '{path}' WITH (FORMAT GDAL, DRIVER 'FlatGeoBuf')",
        )
        return path

    @typechecked
    def ogr_to_gdf(self) -> gpd.GeoDataFrame:
        assert isinstance(self._data, str), (
            f"Data must be a string, got {type(self._data)}"
        )
        geom_column = self.geom_column
        gdf = gpd.read_file(self._data, layer=self.layer)
        if geom_column == "geom":
            gdf.rename(columns={"geom": "geometry"}, inplace=True)
        return gdf

    @typechecked
    def gdf_to_duckdb(
        self,
        con: duckdb.DuckDBPyConnection,
        table_name: str = "temp_table",
    ) -> duckdb.DuckDBPyRelation:
        assert isinstance(self._data, gpd.GeoDataFrame), (
            f"Data must be a GeoDataFrame, got {type(self._data)}"
        )
        # Convert geometry to WKB for DuckDB compatibility
        df_copy = self._data.copy()
        df_copy["geometry_wkb"] = df_copy.geometry.apply(lambda geom: geom.wkb)
        df_copy = df_copy.drop(columns=["geometry"])

        # Register the DataFrame as a temporary table
        con.register(table_name, df_copy)

        # Create a permanent table
        return con.sql(
            f"""
            SELECT * EXCLUDE (geometry_wkb), ST_GeomFromWKB(geometry_wkb) as geometry
            FROM {table_name}
            """
        )

    @property
    def gdf(self):
        if isinstance(self._data, str):
            return self.ogr_to_gdf()
        elif isinstance(self._data, duckdb.DuckDBPyRelation):
            return self.duckdb_to_gdf()
        else:
            to_return = self._data
            if self.geom_column == "geom":
                to_return.rename(columns={"geom": "geometry"}, inplace=True)
            return to_return

    @property
    def duckdb_relation(self):
        if isinstance(self._data, str):
            return self.ogr_to_duckdb(self.con)
        elif isinstance(self._data, duckdb.DuckDBPyRelation):
            fid = f"tmp_{str(uuid.uuid4()).split('-')[0]}"
            return self._data.query(
                virtual_table_name=fid,
                sql_query=f"SELECT * EXCLUDE ({self.geom_column}), {self.geom_column} as geometry FROM {fid}",
            )
        elif isinstance(self._data, gpd.GeoDataFrame):
            return self.gdf_to_duckdb(self.con)
        else:
            raise ValueError(
                f"Data must be a string, DuckDB relation, or GeoDataFrame, got {type(self._data)}"
            )

    @typechecked
    def duckdb_to_pmtiles(self, path: str, tile_opts: TileOpts = TileOpts()) -> str:
        from spatialoperations.vectorops.pmtiles import fgb_to_pmtiles

        assert isinstance(self._data, duckdb.DuckDBPyRelation), (
            f"Data must be a DuckDB relation, got {type(self._data)}"
        )
        fgb = self.duckdb_to_flatgeobuf()
        pmtiles = fgb_to_pmtiles({self.name: fgb}, path, tile_opts=tile_opts)
        return pmtiles
