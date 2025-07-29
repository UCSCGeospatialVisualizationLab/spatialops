import logging
import os
from glob import glob

import yaml

from spatialoperations import SpatialOperations
from spatialoperations.compute import SequentialCompute, get_compute
from spatialoperations.config import SpatialOpsConfig
from spatialoperations.rasterops.intake import RasterIntake
from spatialoperations.rasterops.zarr_manager import prep_array_group
from spatialoperations.types.vectortypes import VectorLike
from spatialoperations.types.xrtypes import RasterLike
from spatialoperations.vectorops.intake import VectorIntake
from spatialoperations.vectorops.utils import create_connection

logger = logging.getLogger("spatialoperations.logger")


def parse_paths(node, directories):
    if "paths" in node:
        paths = node["paths"]
        if "directory" in node:
            paths = [
                os.path.join(directories[node["directory"]], path) for path in paths
            ]
    elif "glob" in node:
        to_glob = node["glob"]
        if "directory" in node:
            to_glob = os.path.join(directories[node["directory"]], to_glob)

        paths = glob(to_glob)
    else:
        raise ValueError(f"No paths or glob found for {node['id']}")
    return paths


def process_node(intake, node, current_group, directories, compute):
    overwrite = node.get("overwrite", False)
    _, current_group = prep_array_group(
        group=current_group, root_group=intake.zarr_manager.root_group
    )
    print(f"Processing node {node}")
    fid = node["id"]
    if node["type"] == "group":
        if overwrite:
            logger.info(f"Deleting {current_group.name}")
            del current_group[fid]

        if fid not in list(current_group.keys()):
            next_group = current_group.create_group(fid)
        else:
            next_group = current_group[fid]
        for child in node["children"]:
            process_node(intake, child, next_group, directories, compute)

    elif node["type"] == "var":
        if overwrite:
            logger.info(f"Deleting {current_group.name}/{node['id']}")
            del current_group[node["id"]]

        # Process paths from a path list or a glob
        paths = parse_paths(node, directories)
        logger.info(f"Paths: {paths}")

        data = {f"{node['id']}_{i}": RasterLike(path) for i, path in enumerate(paths)}

        kwargs = node.get("kwargs", {})
        intake.import_multi_raster_to_zarr_with_prep(
            data=data,
            group=current_group,
            output_path=fid,
            compute=compute,
            **kwargs,
        )


def from_yaml(yaml_path: str):
    with open(yaml_path) as f:
        yaml_config = yaml.safe_load(f)
    so_config = SpatialOpsConfig(**yaml_config["config"])

    so = SpatialOperations(so_config)
    raster_intake = RasterIntake(so_config)
    vector_intake = VectorIntake(so_config)

    if "compute" in yaml_config:
        compute_conf = yaml_config["compute"]
        compute = get_compute(compute_conf["mode"], **compute_conf["kwargs"])
    else:
        compute = SequentialCompute()

    directories = yaml_config.get("directories", {})

    if "raster" in yaml_config:
        raster_config = yaml_config["raster"]
        for raster in raster_config:
            process_node(
                raster_intake,
                raster,
                raster_intake.zarr_manager.root_group,
                directories,
                compute,
            )

    if "vector" in yaml_config:
        con = create_connection()
        vector_config = yaml_config["vector"]
        for vector in vector_config:
            paths = parse_paths(vector, directories)
            data = {
                f"{vector['id']}_{i}": VectorLike(
                    path, name=f"{vector['id']}_{i}", con=con
                )
                for i, path in enumerate(paths)
            }
            vector_intake.multi_write_vector_to_parquet(
                data=data,
                output_name=vector["id"],
                overwrite=vector.get("overwrite", False),
                append_partition_column=vector.get("append_partition_column", None),
                kwargs=vector.get("kwargs", {}),
            )
