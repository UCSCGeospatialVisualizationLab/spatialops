import math

import pyproj
import xarray as xr
import xarray_regrid as xr_regrid
from shapely.geometry import Point
from shapely.ops import transform

from spatialoperations.types.xrtypes import RasterLike


def guess_reasonable_boxbuff(da: RasterLike) -> float:
    crs = da.data.rio.crs
    if crs.is_projected:
        return 1000
    else:
        return 0.2


def conservative_regrid(
    src_da: xr.DataArray,
    tgt_da: xr.DataArray,
    assert_with_epsilon: float | bool = 0.04,
    assert_min_sum: float = 1000,
):
    boxbuff = guess_reasonable_boxbuff(RasterLike(src_da))
    src_da = src_da.rio.clip_box(
        minx=tgt_da.odc.geobox.extent.boundingbox.bbox[0] - boxbuff,
        miny=tgt_da.odc.geobox.extent.boundingbox.bbox[1] - boxbuff,
        maxx=tgt_da.odc.geobox.extent.boundingbox.bbox[2] + boxbuff,
        maxy=tgt_da.odc.geobox.extent.boundingbox.bbox[3] + boxbuff,
    )
    initial_res = get_resolution(src_da)[0]
    target_res = get_resolution(tgt_da)[0]
    regrid = src_da.regrid.conservative(
        tgt_da.drop_vars("spatial_ref"), latitude_coord="y"
    )
    regrid = regrid * (math.pow(target_res, 2) / math.pow(initial_res, 2))
    regrid = regrid.copy(data=regrid.data)
    if assert_with_epsilon:
        src_sum = src_da.sum().values
        if src_sum < assert_min_sum:
            return regrid
        regrid_sum = regrid.sum().values
        if src_sum == 0:
            assert regrid_sum == 0, (
                "Source data sum is 0, but regridded data sum is not 0"
            )
            return regrid
        abs_diff = abs(1 - (regrid_sum / src_sum))
        failure = abs_diff > assert_with_epsilon
        failure_msg = (
            f"Difference between regridded and source data is {abs_diff}, "
            f"src sum is {src_sum}, regrid sum is {regrid_sum}"
        )
        assert not failure, failure_msg
    return regrid


def get_resolution(ds):
    return [abs(ds.x.values[1] - ds.x.values[0]), abs(ds.y.values[1] - ds.y.values[0])]


def qgis_to_bounds_tuple(qgis_bbox: str) -> tuple[float, float, float, float]:
    """Convert a QGIS bounding box string to a tuple of floats."""
    bounds = [
        float(i)
        for i in qgis_bbox.replace("°", "")
        .replace(":", " ")
        .replace(",", "")
        .split(" ")
        if i
    ]
    bottom, left, top, right = bounds
    return left, bottom, right, top


def meters_to_degrees(distance_meters: float, latitude: float) -> float:
    """Translate a distance in meters to degrees, given a latitude.

    Parameters
    ----------
    distance_meters : float
        The distance to convert, in meters.
    latitude : float
        The latitude at which to perform the conversion, in decimal degrees.

    Returns
    -------
    float
        The equivalent distance in degrees.

    """
    # Earth radius in meters
    earth_radius = 6378137.0  # approximate radius in meters

    # Convert latitude from degrees to radians
    lat_radians = math.radians(latitude)

    # Calculate the length of a degree of latitude and longitude at the given latitude
    lat_length = math.cos(lat_radians) * 2.0 * math.pi * earth_radius / 360.0

    # Translate the distance from meters to degrees
    distance_degrees = distance_meters / lat_length

    return distance_degrees


def transform_point(x: float, y: float, crs: str, out_crs: str = "EPSG:4326"):
    pt = Point(x, y)
    init_crs = pyproj.CRS(crs)
    tgt_crs = pyproj.CRS(out_crs)
    project = pyproj.Transformer.from_crs(init_crs, tgt_crs, always_xy=True).transform
    return transform(project, pt)
