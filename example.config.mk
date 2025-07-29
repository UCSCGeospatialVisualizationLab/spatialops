# This file is used to configure a run process of jupyter using Make.
# It is expected to export
# - VOLUME_MOUNTS
# - ENV_FILES
# - JUPYTER_PORT

JUPYTER_PORT = 8890

DEV_SPATIALOPERATIONS = True
MOUNT_CCCR = True
MOUNT_LOCAL_DATA_DIR = False

CCCR_LOCAL_DIR = /cccr-lab
CCCR_DOCKER_DIR = /cccr-lab

DATA_DIR_LOCAL = /SpatialOps_TestData/
DATA_DIR_DOCKER = /data

SITE_PACKAGES_DIR = /opt/conda/lib/python3.12/site-packages

SPATIALOPERATIONS_LOCAL_DIR = /users/chlowrie/geospatial-analysis-environment/
SPATIALOPERATIONS_DOCKER_DIR = /app/

VOLUME_MOUNTS = $(if $(filter True,$(MOUNT_CCCR)),-v $(CCCR_LOCAL_DIR):$(CCCR_DOCKER_DIR)) \
	$(if $(filter True,$(DEV_SPATIALOPERATIONS)), -v $(SPATIALOPERATIONS_LOCAL_DIR):$(SPATIALOPERATIONS_DOCKER_DIR)) \
	$(if $(filter True,$(MOUNT_LOCAL_DATA_DIR)), -v $(DATA_DIR_LOCAL):$(DATA_DIR_DOCKER)) 


USE_NAUTILUS_S3 = True
USE_DATA_ENV = False
USE_PUBLISH_ENV = True

NAUTILUS_S3_ENV_FILE = .env.s3
DATA_ENV_FILE = .env.data
PUBLISH_ENV_FILE = .env.publish

ENV_FILES = $(if $(filter True,$(USE_NAUTILUS_S3)),--env-file $(NAUTILUS_S3_ENV_FILE)) \
	$(if $(filter True,$(USE_DATA_ENV)),--env-file $(DATA_ENV_FILE)) \
	$(if $(filter True,$(USE_PUBLISH_ENV)),--env-file $(PUBLISH_ENV_FILE))
