analysis-build:
	docker build \
		--platform linux/amd64 \
		-t $(IMAGE_NAME)-analysis \
		--build-arg ENVIRONMENT_FILE=environment.yml \
		--build-arg ENVIRONMENT_DIR=$(ENVIRONMENTS_DIR) \
		--build-arg INSTALL_PMTILES=1 \
		-f $(ENVIRONMENTS_DIR)/Dockerfile \
		.

analysis-run:
	docker run \
		--platform linux/amd64 \
		-it \
		--rm \
		$(VOLUME_MOUNTS) \
		$(ENV_FILES) \
		$(IMAGE_NAME)-analysis

analysis-push:
	docker tag $(IMAGE_NAME)-analysis gitlab-registry.nrp-nautilus.io/ucsc-vizlab/spatialops/$(IMAGE_NAME)-analysis:latest
	docker push gitlab-registry.nrp-nautilus.io/ucsc-vizlab/spatialops/$(IMAGE_NAME)-analysis:latest

jupyter-run:
	docker run \
		--platform linux/amd64 \
		-it \
		--rm \
		$(PORTS) \
		$(VOLUME_MOUNTS) \
		$(ENV_FILES) \
		--entrypoint /opt/conda/bin/jupyter \
		$(IMAGE_NAME)-analysis \
		notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --config=/tmp/jupyter_notebook_config.py

jupyter-deploy:
	helm upgrade --install $(USER) charts/jupyter --debug --atomic

jupyter-teardown:
	helm uninstall $(USER)

# Build the project
publish: 
	uv build
	uv publish
