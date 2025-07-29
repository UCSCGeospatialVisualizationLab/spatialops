# from unittest.mock import MagicMock, patch

# import geopandas as gpd
# import numpy as np
# import xarray as xr
# from app import app
# from fastapi.testclient import TestClient
# from shapely import Polygon

# client = TestClient(app)


# def test_read_main():
#     response = client.get("/")
#     assert response.status_code == 200
#     assert response.json() == {"msg": "Hello World"}


# def setup_mock_data():
#     mock_da = xr.DataArray(
#         np.random.rand(256, 256),
#         dims=("y", "x"),
#         coords={"y": np.arange(256), "x": np.arange(256)},
#     )

#     mock_raster_ops = MagicMock()
#     mock_raster_ops.get_single_xarray_tile.return_value = mock_da

#     mock_png_data = b"mock_png_data"

#     return mock_da, mock_raster_ops, mock_png_data


# @patch("app.get_group_and_var")
# @patch("app.get_raster_ops")
# @patch("app.da_to_png")
# def test_get_rgb_tile(mock_da_to_png, mock_get_raster_ops, mock_get_group_and_var):
#     mock_da, mock_raster_ops, mock_png_data = setup_mock_data()
#     mock_get_raster_ops.return_value = mock_raster_ops
#     mock_get_group_and_var.return_value = ("test_group", "test_var")
#     mock_da_to_png.return_value = mock_png_data

#     response = client.get(
#         "/colormap/1/2",
#         params={
#             "color": "viridis",
#             "path": "test/path",
#             "vmax": 100,
#             "vmin": 0,
#             "zarr": "test-bucket/test.zarr",
#         },
#     )

#     assert response.status_code == 200
#     assert response.headers["content-type"] == "image/png"
#     assert response.content == mock_png_data

#     mock_get_group_and_var.assert_called_once_with("test/path")
#     mock_get_raster_ops.assert_called_once_with("test-bucket/test.zarr")
#     mock_raster_ops.get_single_xarray_tile.assert_called_once_with(
#         var="test_var", idx=(1, 2), group="test_group"
#     )
#     mock_da_to_png.assert_called_once_with(mock_da, "viridis", 0, 100)


# @patch("app.get_group_and_var")
# @patch("app.get_raster_ops")
# @patch("app.da_to_elevation_rgb")
# def test_get_elevation_tile(
#     mock_da_to_elevation_rgb, mock_get_raster_ops, mock_get_group_and_var
# ):
#     mock_da, mock_raster_ops, mock_png_data = setup_mock_data()
#     mock_get_raster_ops.return_value = mock_raster_ops
#     mock_get_group_and_var.return_value = ("test_group", "test_var")
#     mock_da_to_elevation_rgb.return_value = mock_png_data

#     response = client.get(
#         "/terrain/1/2",
#         params={
#             "color": "viridis",
#             "path": "test/path",
#             "vmax": 100,
#             "vmin": 0,
#             "zarr": "test-bucket/test.zarr",
#         },
#     )

#     assert response.status_code == 200
#     assert response.headers["content-type"] == "image/png"
#     assert response.content == mock_png_data

#     mock_get_group_and_var.assert_called_once_with("test/path")
#     mock_get_raster_ops.assert_called_once_with("test-bucket/test.zarr")
#     mock_raster_ops.get_single_xarray_tile.assert_called_once_with(
#         var="test_var", idx=(1, 2), group="test_group"
#     )
#     mock_da_to_elevation_rgb.assert_called_once_with(mock_da, 0, 100)


# @patch("app.get_raster_ops")
# @patch("app.get_root_metadata")
# def test_get_metadata(mock_get_root_metadata, mock_get_raster_ops):
#     # Setup mock metadata
#     mock_metadata = {
#         "groups": ["group1", "group2"],
#         "arrays": ["array1", "array2"],
#         "rasterops_config": {
#             "bounds": [0, 0, 100, 100],
#             "chunk_size": 256,
#             "dtype": "float32",
#             "dx": 0.1,
#             "epsg": 4326,
#             "nodata": None,
#         },
#     }
#     mock_get_root_metadata.return_value = mock_metadata

#     # Test without path parameter
#     response = client.get("/metadata", params={"zarr": "test-bucket/test.zarr"})

#     assert response.status_code == 200
#     assert response.headers["content-type"] == "application/JSON"
#     assert response.json() == mock_metadata

#     # Test with path parameter
#     mock_raster_ops = MagicMock()
#     mock_raster_ops.get_metadata.return_value.to_dict.return_value = {
#         "consolidated_metadata": {
#             "metadata": {
#                 "test/path": {
#                     "node_type": "array",
#                     "shape": [256, 256],
#                     "dtype": "float32",
#                 }
#             }
#         }
#     }
#     mock_get_raster_ops.return_value = mock_raster_ops

#     response = client.get(
#         "/metadata", params={"zarr": "test-bucket/test.zarr", "path": "test/path"}
#     )

#     assert response.status_code == 200
#     assert response.headers["content-type"] == "application/JSON"
#     assert response.json() == {
#         "node_type": "array",
#         "shape": [256, 256],
#         "dtype": "float32",
#     }


# @patch("app.get_raster_ops")
# def test_bounding_boxes(mock_get_raster_ops):
#     mock_gdf = gpd.GeoDataFrame(
#         {
#             "x": [1, 2],
#             "y": [3, 4],
#             "geometry": [
#                 Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
#                 Polygon([(1, 1), (2, 1), (2, 2), (1, 2)]),
#             ],
#         },
#         crs="EPSG:4326",
#     )

#     mock_raster_ops = MagicMock()
#     mock_raster_ops.get_covering_polygons.return_value = mock_gdf
#     mock_get_raster_ops.return_value = mock_raster_ops

#     response = client.get("/bounding_boxes", params={"zarr": "test-bucket/test.zarr"})

#     assert response.status_code == 200
#     assert response.json() == [
#         {
#             "idx": {"x": 1, "y": 3},
#             "bounds": {"minx": 0.0, "miny": 0.0, "maxx": 1.0, "maxy": 1.0},
#         },
#         {
#             "idx": {"x": 2, "y": 4},
#             "bounds": {"minx": 1.0, "miny": 1.0, "maxx": 2.0, "maxy": 2.0},
#         },
#     ]

#     mock_get_raster_ops.assert_called_once_with("test-bucket/test.zarr")
#     mock_raster_ops.get_covering_polygons.assert_called_once()
