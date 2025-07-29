## VectorOps

This library wraps DuckDB and Parquet, and provides functionality for managing a collection of geospatial data.  

It primarily consists of the `geoduck` object, which represents a connection with a particular set of remote Parquet files.  

```python
gd = geoduck.VectorOps("s3://cl-lake-test/vector-test")
```

### Importing Data
To import data, use the `intake` attribute on a GeoDuck instance.  Check out tests for more info.

```python
gd.intake.ogr_to_parquet(
    ogr_path=TEST_GADM_MINIMAL,
    parquet_path=PARQUET_PATH,
    partition_by=['GID_0'],
    overwrite=True,
    partition_batch_to_manage_memory=True,
    show_progress=True
)
```

This adds a parquet to the data store, and some basic metadata like the CRS.  There are a few parameters to manage the intake, like partitions and batching.  

### View the Data Store
```python
gd.get_views()
```

### Export to PMTiles
```python
gd.export.run_tippecanoe(
    output_path="s3://cl-lake-test/test-data/results/gadm_410_minimal_from_gdf.pmtiles",
    views=["gadm_410_minimal_from_gdf"]
)
```

It's built to be flexible in what it takes, particularly in being able to take duckdb relations.  For example:
```python
view = gd.con.sql("SELECT * FROM gadm_410 LIMIT 10;")
gd.pmtiles.run_tippecanoe("test", view, names = ["test"])
```

Configurations are done via `TileLayerConfig`, `TippecanoeLayerConfig`, and `TileOpts`.