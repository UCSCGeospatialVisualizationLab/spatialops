LOCAL_DIR = /SpatialOps_TestData

download-test:
	s3cmd get s3://cl-lake-test/test-data/inputs/gadm_410.gpkg /SpatialOps_TestData/vectorops_test/gadm_410.gpkg

upload-test:
	s3cmd sync --recursive /SpatialOps_TestData/vectorops_test/ s3://cl-lake-test/test-data/inputs/

test-spatialops:
	docker run \
		--rm \
		-it \
		-v $(LOCAL_DIR):/data \
		$(ENV_FILES) \
		$(VOLUME_MOUNTS) \
		$(IMAGE_NAME)-analysis:latest \
		python3 -m pytest -v -m "not molokai" tests/spatialops

test-spatialops-ci:
	docker run \
		--rm \
		-v ./tests:/app/tests \
		$(IMAGE_NAME)-analysis:latest \
		python3 -m pytest -m "not molokai and not s3" tests/spatialops

# TEST_TARGETS := test-spatialops test-zarr-server
TEST_TARGETS := test-spatialops
TEST_JOBS ?= $(words $(TEST_TARGETS))

test-all:
	$(MAKE) -j$(TEST_JOBS) $(TEST_TARGETS)
