# SpatialOperations

This repo leverages cloud-native-geospatial (CNG) tooling alongside Kubernetes and S3 infrastructure (currently geared around NRP Nautilus), to create high-performance spatial workflows.

It's original use case was to:
- Unify and mosaic GeoTiffs generated in different UTM projections across a large area.
- Run arbitrary downstream analytics on these formats, including raster computation and raster-vector summarization.
- Be able to apply Bring-Your-Own-Compute (BYOC) on CNG formats.

Some key features:
1. Intake manifests of GeoTiffs and GDAL vectors into Zarr and Parquet. 
  - Integrated support for partitioning, conservative regridding, reprojection.
2. Abstract compute and storage. 
  - Users can roll their own compute to parallelize operations on CNG formats. Existing compute with Dask and Joblib is supported out-of-the-box.
  - Storage can be deployed locally or in any S3-compliant environment.
3. Integrated jupyter notebooks, and deployment of compute nodes with auto-sync of environment and dependencies.
  - This was specifically designed for users who have access to large cloud-based pods, and want to develop on those machines.
4. Manage exports and APIs for visualizing and sharing data via COG and PMTiles. 
  - Designed to facilitate exporting data into high-performance visualization formats.
  - HTTPS servers are also included although not maintained, and there are likely more performant options now.

## Recognition
This repository builds on the fantastic work done by teams in the Cloud-Native-Geospatial space. We particularly want to thank the teams at Earthmover and Development Seed for their work in both developing these high-performance data formats, and for their input in building this library.

## Distribution
The package is distributed using PyPI, and built/published using UV.  It is intended to be installed via conda, which does a good job of managing GDAL as a dependency.

In the future we'll build a conda recipe that manages this better, but currently installing via conda + pip has been effective.  Examples of installation can be found in the environments yaml files.

## Environments
The `environments` directory contains the base environment and any other environments that are needed.

## Publishing Base Environment

### Setting up the `config.mk`
See the example `config.mk`.  This is expected to export two paths at the moment, `VOLUME_MOUNTS` and `ENV_FILES`.  The rest is just to construct these variables.

### Publishing the base environment to PyPI
This requires a `UV_PUBLISH_TOKEN` in `.env.publish`
3. Build the base environment:
```bash
# Build and run the container
make publisher-build
make publisher-run

# Publish to PyPI
make publish
```

This publishes the `spatialoperations` package to PyPI.

## Building the analysis environment

1. Update any conda dependencies in `environments/environment.yml`. This a good place for installing GDAL since conda manages it's binary dependencies.

2. Update any pip dependencies in `pyproject.toml`.

3. Build the analysis environment:
```bash
make analysis-build
make analysis-run
```

## Run the Jupyter Environment locally
```
make jupyter-run
```

# Deploying a pod to Nautilus
This package is designed to run on cloud-infrastructure. It has been specifically designed to run on Nautilus, part of the National Data Platform, but it should be able to be run on other Kubernetes deployments and S3-compliant infrastructure given the right credentials.

## Prerequisites

1. Install `helm` (On MacOSX):
```bash
brew install helm
```
See https://helm.sh/docs/intro/install/ for other systems.

2. Configure AWS credentials:
Create a file named `.env.s3` with your Nautilus Cept S3 credentials.  See `.env.s3.example`, as their may be other variables needed.

## Deployment

Create a deployment with a pod, ingress, and persistent volume unique to you:
```bash
make jupyter-push
make jupyter-deploy
```

Release resources when you're done:
```bash
make jupyter-teardown
```

## Formatting

You can use [ruff](https://docs.astral.sh/ruff/formatter/#ruff-format) to
format your code before committing. The easiest way is to make sure that `uv`
is installed and run `make format`. If you want to make sure that files are
formatted as you save them make sure to install the relevant `ruff` extension
(https://marketplace.cursorapi.com/items?itemName=charliermarsh.ruff for
VSCode/Cursor).

## Developing Dependencies on a deployed Jupyter server

You will need to have `fswatch` installed (`brew install fswatch`). To develop
`spatialoperations` just run:

```
make dev-spatialoperations
```

This command will ensure that there is a server running at
`https://dev-jupyter.nrp-nautilus.io`.

Don't forget to use `importlib` to reload dependencies from disk:

```
import importlib
import rasterops

# If you change a file locally, wait for it to be synced and then run:

importlib.reload(rasterops)

```

If you want to make sure that the dev server is shut down you can just run

```
helm uninstall dev
```
