"""Utilities used by the zarr server."""

import io
import json
import logging
import os
from functools import wraps

import numpy as np
import xarray as xr
from fastapi import HTTPException
from matplotlib import colormaps
from PIL import Image

from spatialoperations.rasterops.rasterops import RasterOps

dev = os.environ.get("ENV") == "dev"
logger = logging.getLogger("zarr_server.api")
logging.basicConfig(
    level=logging.DEBUG if dev else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

UNUSED_ARRAYS = ["x", "y", "spatial_ref"]


class MissingZarrError(Exception):
    """Throw this when we can't load a zarr."""

    pass


def format_color(color: str) -> str:
    """Format color string to account for differences between client-side library.

    Args:
        color (str): Color string to format

    Returns:
        str: Formatted color string

    """
    return color.replace("YI", "Yl")


def get_colormap_key(color_key: str):
    """Fetch a colormap key from matplotlib colormaps, ignoring case.

    Args:
        color_key (str): The color key to search for.

    Returns:
        str: The matched colormap key, or None if not found.

    """
    color_key_lower = color_key.lower()
    for key in colormaps.keys():
        if key.lower() == color_key_lower:
            return key
    return None


def da_to_png(da: xr.DataArray, color: str, vmin: int, vmax: int) -> bytes:
    """Convert elevation data to RGB-encoded PNG for terrain visualization.

    Args:
        da: Input elevation DataArray
        color: Matplotlib color scheme to use
        vmin: Minimum elevation value
        vmax: Maximum elevation value

    Returns:
        RGB-encoded elevation PNG as bytes

    """
    cm = colormaps[get_colormap_key(format_color(color))]

    # Normalize the data to [0,1] range
    da = (da - vmin) / (vmax - vmin)
    # Apply colormap
    rgba = cm(da)
    # Set alpha channel to 0 for NaN values
    rgba[..., 3] = xr.where(da.isnull(), 0, 1)

    # Convert the RGBA array to an image
    img = Image.fromarray((rgba * 255).astype("uint8"), "RGBA")

    # Save the image to a bytes buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Return the image as a response
    return buffer.getvalue()


def da_to_elevation_rgb(da: xr.DataArray, vmin: float, vmax: float) -> bytes:
    """Convert elevation data to RGB-encoded PNG for terrain visualization.

        Following Mapbox's encoding scheme for elevation data, as referenced here:
        https://deck.gl/docs/api-reference/geo-layers/terrain-layer#elevationdecoder


    Args:
        da: Input elevation DataArray
        vmin: Minimum elevation value
        vmax: Maximum elevation value

    Returns:
        RGB-encoded elevation PNG as bytes

    """
    # Scale the normalized values to the full range
    elevation = np.interp(da, [vmin, vmax], [vmin, vmax])

    # Add 10000 to match the decoder's -10000 offset
    elevation = elevation + 10000

    # Calculate RGB values using the decoder's exact scalers:
    # elevation = -10000 + (r * 6553.6 + g * 25.6 + b * 0.1)
    r = (elevation / 6553.6) % 256
    g = (elevation / 25.6) % 256
    b = (elevation / 0.1) % 256

    # Create RGBA array
    rgba = np.zeros((*da.shape, 4), dtype=np.uint8)
    rgba[..., 0] = r.astype(np.uint8)  # Red channel
    rgba[..., 1] = g.astype(np.uint8)  # Green channel
    rgba[..., 2] = b.astype(np.uint8)  # Blue channel
    rgba[..., 3] = 255  # Full opacity

    # Set alpha channel to 0 for NaN values
    rgba[np.isnan(da), 3] = 0

    # Convert the RGBA array to an image
    img = Image.fromarray(rgba, "RGBA")

    # Save the image to a bytes buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Return the image as a response
    return buffer.getvalue()


def memoize(func):
    """Cache function results to avoid redundant computations.

    Args:
        func: Function to memoize

    Returns:
        Wrapper function with caching capability

    """
    cache = {}

    def wrapper(*args):
        if args in cache:
            return cache[args]
        else:
            result = func(*args)
            cache[args] = result
            return result

    return wrapper


def handle_missing_zarr(func):
    """Handle exceptions raised by get_raster_ops and return a FastAPI 400 error."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MissingZarrError as e:
            raise HTTPException(status_code=400, detail="Could not load zarr") from e

    return wrapper


@memoize
def get_raster_ops(path: str):
    """Retrieve and cache RasterOps from S3 zarr store.

    Args:
        path: Path to zarr store

    Returns:
        RasterOps object

    """
    try:
        return RasterOps.from_zarr(f"s3://{path}")
    except Exception as e:
        # Note that we raise, rather than making this return None, so that nothing is
        # stored in the cache. If this path did not previously exist but it is created
        # then this method will start working.
        raise MissingZarrError from e


def get_group_and_var(path: str):
    """Extract the zarr group and variable name from a path string.

    Args:
        path (str): A path string containing a group and variable name separated by '/',
                   e.g. 'group_name/variable_name'

    Returns:
        tuple[str, str]: A tuple containing:
            - The group name (str): The part of the path before the '/'
            - The variable name (str): The part of the path after the '/'

    Example:
        >>> get_group_and_var("temperature/mean")
        ('temperature', 'mean')

    """
    index = path.find("/")
    return path[:index], path[index + 1 :]


def last_segment(s: str):
    """Extract and format root level metadata.

    Args:
        s: String to split

    Returns:
        The last segment of the path, after `/`

    """
    return s.split("/")[-1]


def get_root_metadata(rasterops: RasterOps):
    """Extract and format root level metadata.

    Args:
        rasterops: RasterOps object to get metadata for

    Returns:
        Formatted dict of groups, arrays, and config

    """
    metadata = rasterops.get_metadata().to_dict()
    groups = []
    arrays = []
    if metadata["consolidated_metadata"] is None:
        return None
    hierarchy = metadata["consolidated_metadata"]["metadata"]
    for key, value in hierarchy.items():
        if value["node_type"] == "group":
            groups.append(key)
        elif value["node_type"] == "array" and last_segment(key) not in UNUSED_ARRAYS:
            arrays.append(key)

    rasterops_config = json.loads(metadata["attributes"]["rasterops_config"])
    if np.isnan(rasterops_config["nodata"]):
        rasterops_config["nodata"] = None

    return {
        "groups": groups,
        "arrays": arrays,
        "rasterops_config": rasterops_config,
    }
