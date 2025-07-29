import geopandas as gpd
import odc.geo.xr
import rasterio
import xarray as xr
from shapely.geometry import shape


def extract_z_values(
    ds: xr.DataArray,
    gdf: gpd.GeoDataFrame,
    column_name: str,
    offset_column: str = None,
    offset_units: str = None,
) -> gpd.GeoDataFrame:
    # note the extra 'z' dimension that our results will be organized along
    gdf = gdf.copy()
    da_x = xr.DataArray(gdf.geometry.x.values, dims=["z"])
    da_y = xr.DataArray(gdf.geometry.y.values, dims=["z"])
    results = ds.sel(x=da_x, y=da_y, method="nearest")
    gdf[column_name] = results.values
    gdf.loc[gdf[column_name] == ds.rio.nodata, column_name] = 0
    gdf.loc[gdf[column_name].isna(), column_name] = 0
    return gdf


def add_geobox(ds, crs=None):
    """
    Ensure that an xarray DataArray has a GeoBox and .odc.* accessor
    using `odc.geo`.

    If `ds` is missing a Coordinate Reference System (CRS), this can be
    supplied using the `crs` param.

    Parameters
    ----------
    ds : xarray.Dataset or xarray.DataArray
        Input xarray object that needs to be checked for spatial
        information.
    crs : str, optional
        Coordinate Reference System (CRS) information for the input `ds`
        array. If `ds` already has a CRS, then `crs` is not required.
        Default is None.

    Returns
    -------
    xarray.Dataset or xarray.DataArray
        The input xarray object with added `.odc.x` attributes to access
        spatial information.

    """
    # If a CRS is not found, use custom provided CRS
    init_crs = ds.rio.crs
    if ds.odc.crs is None and crs is not None:
        ds = ds.odc.assign_crs(crs)
        ds.rio.write_crs(init_crs, inplace=True)
    elif ds.odc.crs is None and crs is None:
        raise ValueError(
            "Unable to determine `ds`'s coordinate "
            "reference system (CRS). Please provide a "
            "CRS using the `crs` parameter "
            "(e.g. `crs='EPSG:3577'`)."
        )

    return ds


def xr_vectorize(
    da,
    coarsen_by=1,
    attribute_col=None,
    crs=None,
    dtype="float32",
    output_path=None,
    verbose=True,
    filter_to_positive=False,
    **rasterio_kwargs,
) -> gpd.GeoDataFrame:
    """
    Vectorises a raster ``xarray.DataArray`` into a vector
    ``geopandas.GeoDataFrame``.

    Parameters
    ----------
    da : xarray.DataArray
        The input ``xarray.DataArray`` data to vectorise.
    attribute_col : str, optional
        Name of the attribute column in the resulting
        ``geopandas.GeoDataFrame``. Values from ``da`` converted
        to polygons will be assigned to this column. If None,
        the column name will default to 'attribute'.
    crs : str or CRS object, optional
        If ``da``'s coordinate reference system (CRS) cannot be
        determined, provide a CRS using this parameter.
        (e.g. 'EPSG:3577').
    dtype : str, optional
         Data type  of  must be one of int16, int32, uint8, uint16,
         or float32
    output_path : string, optional
        Provide an optional string file path to export the vectorised
        data to file. Supports any vector file formats supported by
        ``geopandas.GeoDataFrame.to_file()``.
    verbose : bool, optional
        Print debugging messages. Default True.
    **rasterio_kwargs :
        A set of keyword arguments to ``rasterio.features.shapes``.
        Can include `mask` and `connectivity`.

    Returns
    -------
    gdf : geopandas.GeoDataFrame

    """

    # Add GeoBox and odc.* accessor to array using `odc-geo`
    da = add_geobox(da, crs)
    if filter_to_positive:
        da = xr.where(da > 0, 1, 0)
    da = da.coarsen(x=coarsen_by, y=coarsen_by, boundary="pad").max()

    # Run the vectorizing function
    vectors = list(
        rasterio.features.shapes(
            source=da.data.astype(dtype), transform=da.odc.transform, **rasterio_kwargs
        )
    )

    # Extract the polygon coordinates and values from the list
    polygons = [polygon for polygon, value in vectors]
    values = [value for polygon, value in vectors]

    # Convert polygon coordinates into polygon shapes
    polygons = [shape(polygon) for polygon in polygons]

    # Create a geopandas dataframe populated with the polygon shapes
    attribute_name = attribute_col if attribute_col is not None else "attribute"
    gdf = gpd.GeoDataFrame(
        data={attribute_name: values}, geometry=polygons, crs=da.odc.crs
    )

    # If a file path is supplied, export to file
    if output_path is not None:
        if verbose:
            print(f"Exporting vector data to {output_path}")
        gdf.to_file(output_path)

    gdf.sindex
    if filter_to_positive:
        return gdf[gdf["attribute"] == 1.0]
    else:
        return gdf
