# Define paths at the top
ENVIRONMENTS_DIR := environment

# Include other Makefiles
-include $(ENVIRONMENTS_DIR)/environment.mk
-include config.mk
-include tests/test.mk
-include services/zarr_server/Makefile

.PHONY: build run shell clean

.ONESHELL:

# Image name
IMAGE_NAME = geospatial
ENVIRONMENT_FILE = environment.yml
ENTRYPOINT = /bin/bash

# Login to GitHub Container Registry
docker-login:
	bash deployment/docker-login.sh

set-namespace:
	bash deployment/set-default-namespace.sh

dev-spatialoperations:
	./scripts/dev spatialoperations

teardown-dev:
	helm uninstall dev-$(USER)

make format:
	uvx ruff format
 
make dependencies:
	uv pip compile --output-file uv.lock  pyproject.toml

copy-files:
	chmod +x ./scripts/copy_to_storage.py
	@if [ -z "$(SRC)" ]; then \
		echo "Error: SRC parameter is required"; \
		echo "Usage: make jupyter-copy-files SRC=<local_path> [DEST=<remote_path>] [DEPLOYMENT=user] [DEV=true|false]"; \
		exit 1; \
	fi
	@DEPLOY_ARG=""; \
	DEV_ARG=""; \
	if [ "$(DEV)" = "true" ]; then \
		DEV_ARG="--dev"; \
	elif [ ! -z "$(DEPLOYMENT)" ]; then \
		DEPLOY_ARG="--deployment $(DEPLOYMENT)"; \
	fi; \
	REMOTE_ARG=""; \
	if [ ! -z "$(DEST)" ]; then \
		REMOTE_ARG="--remote-path $(DEST)"; \
	fi; \
	./scripts/copy_to_storage.py "$(SRC)" $$REMOTE_ARG $$DEPLOY_ARG $$DEV_ARG
