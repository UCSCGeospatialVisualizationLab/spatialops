build-cog-server:
	docker build \
		-f Dockerfile \
		--platform linux/amd64 \
		--build-arg AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
		--build-arg AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
		--build-arg AWS_S3_ENDPOINT=$AWS_S3_ENDPOINT \
		-t gitlab-registry.nrp-nautilus.io/ucsc-vizlab/spatialops/cog-server .

push-cog-server:
	docker push gitlab-registry.nrp-nautilus.io/ucsc-vizlab/spatialops/cog-server

helm-upgrade-cog-server:
	helm upgrade --install cog-server charts/cog-server --atomic --debug

deploy-cog-server: build-cog-server push-cog-server helm-upgrade-cog-server

develop-cog-server:
	docker run -it --rm -p 8080:8080 \
		--name cog-server-dev \
		-e ENV=dev \
		-e AWS_S3_ENDPOINT=$AWS_S3_ENDPOINT \
		-e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
		-e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
		-v $(PWD):/app \
		gitlab-registry.nrp-nautilus.io/ucsc-vizlab/spatialops/cog-server:latest
