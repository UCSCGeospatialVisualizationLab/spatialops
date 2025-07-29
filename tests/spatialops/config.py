import os

from spatialoperations.config import SpatialOpsConfig
from spatialoperations.types.vectortypes import VectorLike

test_config = {
    "root": "s3://cl-lake-test/spatialops-test",
    "dx": 0.00026977476123492776,
    "epsg": 4326,
    "bounds": [-74.754, 15.921, -67.275, 21.144],
    "chunk_size": 1000,
}

so_config = SpatialOpsConfig(**test_config)
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
sample_da_str = os.path.join(
    TEST_DATA_DIR,
    "rasters",
    "multiintake",
    "DOM_01_S1CC_F_20500p500_CU000_CU000_RP050_hmax.tif",
)

sample_da_str2 = os.path.join(
    TEST_DATA_DIR,
    "rasters",
    "multiintake",
    "DOM_02_S1CC_F_20500p500_CU000_CU000_RP050_hmax.tif",
)

gadm_str = os.path.join(TEST_DATA_DIR, "vectors", "gadm_minimal.gpkg")

benthic = {
    "dom_01": os.path.join(TEST_DATA_DIR, "vectors", "DOM_01", "benthic.shp"),
    "dom_02": os.path.join(TEST_DATA_DIR, "vectors", "DOM_02", "benthic.shp"),
}
