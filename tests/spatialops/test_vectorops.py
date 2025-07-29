import duckdb
import geopandas as gpd
import pytest
from typeguard import typechecked

from spatialoperations.helpers import from_yaml
from spatialoperations.types.vectortypes import VectorLike
from spatialoperations.vectorops.intake import VectorIntake
from spatialoperations.vectorops.utils import create_connection
from spatialoperations.vectorops.vectorops import VectorOps
from tests.log import logger
from tests.spatialops.config import benthic, gadm_str, so_config


@pytest.fixture(scope="session")
def vectorops():
    return VectorOps(so_config)


@pytest.fixture(scope="session")
def vectorlike_from_string():
    return VectorLike(gadm_str, name="gadm", con=create_connection())


@pytest.fixture(scope="session")
def vectorlike_from_duckdb(vectorlike_from_string):
    return VectorLike(vectorlike_from_string.duckdb_relation, name="gadm")


@pytest.fixture(scope="session")
def vectorlike_from_gdf(vectorlike_from_string):
    return VectorLike(vectorlike_from_string.gdf, name="gadm", con=create_connection())


@pytest.fixture(scope="session")
def all_vectorlikes(
    vectorlike_from_string, vectorlike_from_duckdb, vectorlike_from_gdf
):
    return [vectorlike_from_string, vectorlike_from_duckdb, vectorlike_from_gdf]


@typechecked
def assert_geom_column_name(v: VectorLike, expected_name: str = "geometry"):
    assert v.geom_column == expected_name, (
        f"Expected {expected_name}, got {v.geom_column}"
    )


def test_vectorlike_columns(
    vectorlike_from_string, vectorlike_from_duckdb, vectorlike_from_gdf
):
    assert_geom_column_name(vectorlike_from_string, "geom")
    assert_geom_column_name(vectorlike_from_duckdb)
    assert_geom_column_name(vectorlike_from_gdf)
    ddb = vectorlike_from_string.duckdb_relation
    v_ddb = VectorLike(ddb, name="gadm")
    assert_geom_column_name(v_ddb)


def test_vectorlike_from_string_to_gdf(vectorlike_from_string):
    gdf = vectorlike_from_string.gdf
    assert isinstance(gdf, gpd.GeoDataFrame)
    v = VectorLike(gdf, name="test")
    assert_geom_column_name(v)


def test_vectorlike_from_duckdb_to_gdf(vectorlike_from_duckdb):
    gdf = vectorlike_from_duckdb.gdf
    assert isinstance(gdf, gpd.GeoDataFrame)
    v = VectorLike(gdf, name="test")
    assert_geom_column_name(v)


def test_vectorlike_from_gdf_to_gdf(vectorlike_from_gdf):
    gdf = vectorlike_from_gdf.gdf
    assert isinstance(gdf, gpd.GeoDataFrame)
    v = VectorLike(gdf, name="test")
    assert_geom_column_name(v)


def test_vectorlike_from_string_to_duckdb(vectorlike_from_string):
    ddb = vectorlike_from_string.duckdb_relation
    v_ddb = VectorLike(ddb, name="gadm")
    assert isinstance(v_ddb.duckdb_relation, duckdb.DuckDBPyRelation)
    assert_geom_column_name(v_ddb)


def test_vectorlike_from_duckdb_to_duckdb(vectorlike_from_duckdb):
    ddb = vectorlike_from_duckdb.duckdb_relation
    v_ddb = VectorLike(ddb, name="gadm")
    assert isinstance(v_ddb.duckdb_relation, duckdb.DuckDBPyRelation)
    assert_geom_column_name(v_ddb)


def test_vectorlike_from_gdf_to_duckdb(vectorlike_from_gdf):
    ddb = vectorlike_from_gdf.duckdb_relation
    v_ddb = VectorLike(ddb, name="gadm")
    assert isinstance(v_ddb.duckdb_relation, duckdb.DuckDBPyRelation)
    assert_geom_column_name(v_ddb)


def test_reprojected_vectorlike(all_vectorlikes):
    con = create_connection()
    for v in all_vectorlikes:
        x = VectorLike(
            v.get_reprojected(crs="EPSG:2163", source_crs="EPSG:4326"), name="gadm"
        )
        assert_geom_column_name(x)


@pytest.mark.s3
def test_multi_intake2(vectorops):
    data = {k: VectorLike(v, con=vectorops.con) for k, v in benthic.items()}
    vectorops.intake.multi_write_vector_to_parquet(
        data,
        "benthic",
        overwrite=True,
        append_partition_column="region",
    )


def test_flatgeobuf_export(vectorlike_from_string):
    import os

    ddb = vectorlike_from_string.duckdb_relation
    v_ddb = VectorLike(ddb, name="gadm")
    output_path = v_ddb.duckdb_to_flatgeobuf()
    assert os.path.exists(output_path)


@pytest.mark.molokai
def test_import_multi_raster_to_zarr_with_prep_from_yaml3():
    from spatialoperations.helpers import from_yaml

    from_yaml("tests/yamls/habitat.yaml")
