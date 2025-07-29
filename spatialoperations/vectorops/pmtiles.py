"""Provides functionality for exporting vector data to PMTiles format.

The module follows a layered architecture:

1. High-level functions:
   - export_gdf_to_pmtiles: Convert a GeoDataFrame directly to PMTiles

2. Core functionality:
   - run_tippecanoe: Run tippecanoe on GeoJSON files to create PMTiles
   - _run_subprocess_with_output: Utility for running subprocesses with output capture

3. Configuration:
   - TileLayerConfig: Configuration class for PMTiles layer settings and operations

The typical workflow is:
1. Data is loaded into DuckDB (either from GeoDataFrame or existing view)
2. Data is exported to GeoJSON (intermediate format)
3. tippecanoe is run on the GeoJSON to create PMTiles
4. The PMTiles file is moved to its final destination (local or S3)
"""

import copy
import logging
import os
import tempfile
from dataclasses import dataclass

from typeguard import typechecked

from spatialoperations.utils.subprocess import (
    move_file_to_destination,
    run_subprocess_with_output,
)

logger = logging.getLogger("spatialoperations.logger")


class TileLayerConfig:
    """Configuration for a PMTiles layer."""

    def __init__(self, name: str, min_zoom: int = None, max_zoom: int = None):
        """Initialize a layer configuration.

        Args:
            name: Name of the layer
            min_zoom: Minimum zoom level for the layer
            max_zoom: Maximum zoom level for the layer

        """
        self.name = name
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom

    def get_tippecanoe_args(self, geojson_path: str) -> list[str]:
        """Get tippecanoe arguments for this layer.

        Args:
            geojson_path: Path to the GeoJSON file for this layer

        Returns:
            List of tippecanoe arguments for this layer

        """
        layer_opts = []
        if self.min_zoom is not None:
            layer_opts.append(f"minimum_zoom={self.min_zoom}")
        if self.max_zoom is not None:
            layer_opts.append(f"maximum_zoom={self.max_zoom}")

        layer_arg = f"{self.name}:{geojson_path}"
        if layer_opts:
            layer_arg += f":{','.join(layer_opts)}"

        return ["-L", layer_arg]


@dataclass
class TileOpts:
    args: list[str] | None = None
    kwargs: dict | None = None

    def get_opts(self):
        opts = copy.deepcopy(self.args)
        if opts is None:
            opts = ["-zg", "--drop-densest-as-needed", "--force", "--read-parallel"]
        if self.kwargs is not None:
            for k, v in self.kwargs.items():
                if not k.startswith("--"):
                    k = f"--{k}"
                opts.append(f"{k}={v}")
        return opts


@dataclass
class TippecanoeLayerConfig:
    args: dict = None
    name: str | None = None
    source: str | None = None

    def __post_init__(self):
        if self.args is None:
            # TODO this currently doesn't support per-layer attributes particularly well
            self.args = {}

    def get_args(self, geojson_path: str | None = None, name: str | None = None):
        name = name or self.name
        geojson_path = geojson_path or self.source

        if name is None:
            raise ValueError("name must be provided")

        if geojson_path is None:
            raise ValueError("geojson_path must be provided")

        layer_opts = []
        for arg, value in self.args.items():
            if value is not None:
                layer_opts.append(f"{arg}={value}")
            else:
                layer_opts.append(arg)

        layer_arg = f"{name}:{geojson_path}"
        if layer_opts:
            layer_arg += f":{','.join(layer_opts)}"

        return ["-L", layer_arg]


@typechecked
def fgb_to_pmtiles(
    fgb_name_to_path_mapping: dict[str, str],
    output_path: str,
    tile_opts: TileOpts = TileOpts(),
    cleanup: bool = True,
):
    args = []
    for name, path in fgb_name_to_path_mapping.items():
        lc = TippecanoeLayerConfig(name=name, source=path)
        args.extend(lc.get_args())

    temp_path = tempfile.NamedTemporaryFile(suffix=".pmtiles").name
    cmd = ["tippecanoe"] + args + ["-o", temp_path] + tile_opts.get_opts()
    run_subprocess_with_output(cmd)

    move_file_to_destination(temp_path, output_path)

    if cleanup:
        os.remove(temp_path)

    return output_path
