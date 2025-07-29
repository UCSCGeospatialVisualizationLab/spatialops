BRANCH_NAME := $(shell git rev-parse --abbrev-ref HEAD)
ZARR_SERVER_IMAGE_NAME := gitlab-registry.nrp-nautilus.io/ucsc-vizlab/spatialops/zarr-server
ZARR_SERVER_TAG_NAME := $(if $(filter main,$(BRANCH_NAME)),latest,$(BRANCH_NAME))
ZARR_SERVER_CHART_NAME := $(if $(filter main,$(BRANCH_NAME)),zarr-server,zarr-server-$(BRANCH_NAME))
ZARR_SERVER_VALUES := $(if $(filter main,$(BRANCH_NAME)),values.yaml,dev-values.yaml)

build-zarr-server:
	docker build \
		-f zarr_server.Dockerfile \
		--platform linux/amd64 \
		-t $(ZARR_SERVER_IMAGE_NAME):$(ZARR_SERVER_TAG_NAME) .

push-zarr-server:
	docker push $(ZARR_SERVER_IMAGE_NAME):$(ZARR_SERVER_TAG_NAME)

clean:
	rm -rf coverage

helm-upgrade-zarr-server:
	helm upgrade --install $(ZARR_SERVER_CHART_NAME) services/zarr_server/charts/zarr-server \
		--atomic \
		--debug \
		-f services/zarr_server/charts/zarr-server/$(ZARR_SERVER_VALUES)\
		--set image.tag=$(ZARR_SERVER_TAG_NAME) \

deploy-zarr-server: build-zarr-server push-zarr-server helm-upgrade-zarr-server

develop-zarr-server: build-zarr-server
	docker run -it --rm -p 8080:8080 \
		--env-file .env.s3 \
		-e ENV=dev \
		--name zarr-server-dev \
		-p 8000:8000 \
		-v $(PWD)/services/zarr_server/app.py:/app/app.py \
		-v $(PWD)/services/zarr_server/zarr_server_utils.py:/app/zarr_server_utils.py \
		-v $(PWD)/spatialoperations:/app/spatialoperations \
		$(ZARR_SERVER_IMAGE_NAME):$(ZARR_SERVER_TAG_NAME)

build-test-image: build-zarr-server
	docker build \
		-f zarr_server_test.Dockerfile \
		--platform linux/amd64 \
		-t zarr-server-test .

test-zarr-server: build-test-image
	docker run --rm \
		-e ENV=test \
		zarr-server-test \
		pytest

build-test-image-ci:
	docker buildx build \
		--cache-to type=gha \
		--cache-from type=gha \
		-f zarr_server_test.Dockerfile \
		--platform linux/amd64 \
		.

test-zarr-server-ci: build-zarr-server build-test-image-ci
	docker run --rm \
		-e ENV=test \
		zarr-server-test \
		pytest