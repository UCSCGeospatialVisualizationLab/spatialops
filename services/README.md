# Deprecated: Services for Zarr and COG Access

**Disclaimer:**  
This directory contains legacy code for services that provide access to Zarr and Cloud-Optimized GeoTIFF (COG) data over HTTPS. These services are **deprecated** and may not be compatible with the latest versions of the geospatial-analysis-environment or its dependencies. The code is retained here for reference and potential future use, but is not actively maintained.

---

## `cog_server`

The `cog_server` subdirectory was designed to serve Cloud-Optimized GeoTIFFs (COGs) over HTTP(S). It typically used Python-based web frameworks (such as FastAPI or Flask) to provide endpoints for reading and streaming COG data. The server leveraged libraries like `rasterio` and `rio-tiler` for efficient access to geospatial raster data, and may have included support for tile-based requests and basic visualization.

**Key dependencies:**
- `rasterio`: For reading and processing raster data.
- `rio-tiler`: For serving map tiles from COGs.
- `fastapi` or `flask`: For the web API.
- `uvicorn` or `gunicorn`: For running the ASGI/WSGI server.

**Note:**  
The COG server is not actively maintained and may not work with the latest versions of its dependencies. Updating to `titiler` would be appropriate in the future.

---

## `zarr_server`

The `zarr_server` subdirectory provided an HTTP(S) API for accessing Zarr-formatted datasets, which are commonly used for chunked, compressed, N-dimensional arrays. The server exposed endpoints for retrieving metadata, array chunks, and possibly for basic data exploration. It was intended to facilitate remote access to large geospatial datasets stored in Zarr format.

**Key dependencies:**
- `zarr`: For reading and writing Zarr arrays.
- `numcodecs`: For handling compression codecs used in Zarr.
- `fastapi` or `flask`: For the web API.
- `uvicorn` or `gunicorn`: For serving the API.
- `s3fs` or `gcsfs` (optional): For accessing Zarr data stored on cloud object storage.

**Note:**  
The Zarr server is also deprecated and may require updates to function with current versions of the geospatial-analysis-environment or its dependencies.

---

**For current and supported solutions, please refer to the main project documentation or contact the maintainers.**
