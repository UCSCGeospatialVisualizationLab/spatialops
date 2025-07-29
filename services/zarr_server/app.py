"""FastAPI server for serving PNG's of geospatial data from Zarr archives in S3."""

import json
from typing import Annotated

import fastapi
import uvicorn
from fastapi import Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from zarr.core.metadata.v3 import V3JsonEncoder
from zarr_server_utils import (
    da_to_elevation_rgb,
    da_to_png,
    dev,
    get_group_and_var,
    get_raster_ops,
    get_root_metadata,
    handle_missing_zarr,
)

DEFAULT_BUCKET = "vizlab-geodatalake-exports"

app = fastapi.FastAPI(
    summary="""A geospatial server for serving data held in Zarr format
    (https://zarr.readthedocs.io) as PNG's.
    """,
    description="""Zarr is both a storage format and a library for efficiently handling
N-dimensional arrays of data. It's particularly useful when working with data that's
too large to fit in memory.

Key features:

- Chunked storage: Data is split into manageable chunks, allowing you to work with
only the pieces you need
- Compression: Each chunk can be independently compressed using various algorithms
(blosc, gzip, etc.)
- Parallelization: Multiple processes can read/write different chunks simultaneously
- Hierarchical organization: Arrays are organized in groups (similar to directories
  in a filesystem)
- Cloud-native: Works well with distributed storage systems like S3, GCS, or Azure
Blob Storage

Zarr is especially popular in scientific computing, geospatial analysis, and machine
learning where datasets can reach terabyte or petabyte scale. It's conceptually
similar to HDF5 but designed with cloud storage and concurrency in mind.

This API offers the ability to query data stored in Zarr format without having to worry
about to deal with the zarr format or libraries directly. Instead, this API takes a set
of parameters which point at a Zarr (it can be any Zarr that is uploaded to Nautilus' S3
storage, parameterized as `bucket` in most endpoints, and defaults to
`vizlab-geodatalake-exports`), and can return a slice of any array in that zarr encoded
into a PNG.

Most endpoints also take a `zarr` and `path` parameter. The `zarr` parameter should be
the root folder of the zarr data inside of the given bucket, and the `path` should be
the hierarchy path to access the specific array you are interested in. To learn more
about how Zarr hierarchies work, you can read more at
https://zarr.readthedocs.io/en/stable/quickstart.html#hierarchical-groups.
    """,
)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"],
)

# common parameters
gapfill_param = Query(
    False,
    description="Whether to fill gaps in data",
)
path_param = Query(
    ...,
    description="Path to zarr group and variable, e.g. 'group/variable'",
    openapi_examples={
        "caribbean-elevation": {
            "summary": "Caribbean Elevation",
            "description": "Getting elevation from a caribbean elevation zarr",
            "value": "bathymetry/ACA/USA_FL_08",
        }
    },
)
vmax_param = Query(
    ...,
    description="Maximum value for colormap normalization",
    openapi_examples={
        "caribbean-elevation": {
            "summary": "Caribbean Elevation",
            "description": "Getting elevation from a caribbean elevation zarr",
            "value": 10,
        }
    },
)
vmin_param = Query(
    ...,
    description="Minimum value for colormap normalization",
    openapi_examples={
        "caribbean-elevation": {
            "summary": "Caribbean Elevation",
            "description": "Getting elevation from a caribbean elevation zarr",
            "value": -10,
        }
    },
)
x_param = Path(
    ...,
    description="Tile X coordinate",
    openapi_examples={
        "caribbean-elevation": {
            "summary": "Caribbean Elevation",
            "description": "Getting elevation from a caribbean elevation zarr",
            "value": 27,
        }
    },
)
y_param = Path(
    ...,
    description="Tile Y coordinate",
    openapi_examples={
        "caribbean-elevation": {
            "summary": "Caribbean Elevation",
            "description": "Getting elevation from a caribbean elevation zarr",
            "value": 65,
        }
    },
)
zarr_param = Query(
    ...,
    description="The root folder of the zarr, the first segment is the bucket",
    openapi_examples={
        "caribbean-elevation": {
            "summary": "Caribbean Elevation",
            "description": "Getting elevation from a caribbean elevation zarr",
            "value": "cl-lake-test/caribbean-elevation2.zarr",
        }
    },
)
color_param = Query(
    ...,
    description="Matplotlib colormap name",
    openapi_examples={
        "caribbean-elevation": {
            "summary": "Caribbean Elevation",
            "description": "Getting elevation from a caribbean elevation zarr",
            "value": "viridis",
        }
    },
)


@app.get("/")
def read_root():
    """Return a static JSON object, can be used for a health check."""
    return {"msg": "Hello World"}


@app.get("/colormap/{x}/{y}")
@handle_missing_zarr
def get_rgb_tile(
    x: int = x_param,
    y: int = y_param,
    color: str = color_param,
    path: str = path_param,
    vmax: int = vmax_param,
    vmin: int = vmin_param,
    zarr: str = zarr_param,
):
    """Get a colormap-rendered tile at specified coordinates."""
    idx = (x, y)
    group, var = get_group_and_var(path)
    da = get_raster_ops(zarr).get_single_xarray_tile(var=var, idx=idx, group=group)
    return Response(da_to_png(da, color, vmin, vmax), media_type="image/png")


@app.get("/terrain/{x}/{y}")
@handle_missing_zarr
def get_elevation_tile(
    x: int = x_param,
    y: int = y_param,
    gapfill: bool = gapfill_param,
    path: str = path_param,
    vmax: int = vmax_param,
    vmin: int = vmin_param,
    zarr: str = zarr_param,
):
    """Get a terrain-encoded tile at specified coordinates."""
    idx = (int(x), int(y))
    group, var = get_group_and_var(path)

    da = get_raster_ops(zarr).get_single_xarray_tile(var=var, idx=idx, group=group)
    if gapfill:
        da = da.rio.interpolate_na()
    return Response(da_to_elevation_rgb(da, vmin, vmax), media_type="image/png")


@app.get("/metadata")
@handle_missing_zarr
def get_metadata(
    zarr: str = zarr_param,
    path: Annotated[str | None, path_param] = None,
):
    """Retrieve metadata for zarr dataset."""
    ro = get_raster_ops(zarr)
    metadata = get_root_metadata(ro)
    if path is not None:
        metadata = ro.get_metadata().to_dict()["consolidated_metadata"]["metadata"][
            path
        ]

    return Response(
        content=json.dumps(
            metadata,
            cls=V3JsonEncoder,
        ),
        media_type="application/JSON",
    )


@app.get("/bounding_boxes")
@handle_missing_zarr
def bounding_boxes(zarr: str = zarr_param):
    """Get tile bounding boxes for zarr dataset."""
    gdf = get_raster_ops(zarr).get_covering_polygons()
    idxs = gdf.apply(lambda row: {"x": row["x"], "y": row["y"]}, axis=1)
    bounds = gdf.apply(lambda row: row.geometry.bounds, axis=1)
    bounds = [
        {"minx": bound[0], "miny": bound[1], "maxx": bound[2], "maxy": bound[3]}
        for bound in bounds
    ]
    data = list(zip(list(idxs), list(bounds), strict=False))
    data = [{"idx": idx, "bounds": bounds} for idx, bounds in data]
    return JSONResponse(content=data)


@app.get("/get_data_by_bounding_box")
@handle_missing_zarr
def get_data_by_bounding_box(
    color: str = color_param,
    gapfill: bool = gapfill_param,
    maxx: float = Query(..., description="Maximum X coordinate"),
    maxy: float = Query(..., description="Maximum Y coordinate"),
    minx: float = Query(..., description="Minimum X coordinate"),
    miny: float = Query(..., description="Minimum Y coordinate"),
    path: str = path_param,
    terrain: bool = Query(
        False, description="Whether to render as terrain (elevation)"
    ),
    vmax: int = vmax_param,
    vmin: int = vmin_param,
    zarr: str = zarr_param,
):
    """Extract and visualize data within specified bounding box."""
    dc = get_raster_ops(zarr)
    group, var = get_group_and_var(path)
    idxs = list(dc.tiles_by_bounds(left=minx, bottom=miny, right=maxx, top=maxy))
    da = dc.export.as_da(var=var, group=group, idxs=idxs)
    da = da.rio.clip_box(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
    if gapfill:
        da = da.rio.interpolate_na()

    if terrain:
        return da_to_elevation_rgb(da, vmin=vmin, vmax=vmax)

    return da_to_png(da, color=color, vmin=vmin, vmax=vmax)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=dev)
