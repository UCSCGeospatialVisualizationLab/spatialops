from dataclasses import dataclass

import pyproj
import xarray as xr
from odc.geo.geobox import BoundingBox
from shapely.geometry import Point
from shapely.ops import transform


def transform_point(x: float, y: float, crs: str, out_crs: str = "EPSG:4326"):
    pt = Point(x, y)
    init_crs = pyproj.CRS(crs)
    tgt_crs = pyproj.CRS(out_crs)
    project = pyproj.Transformer.from_crs(init_crs, tgt_crs, always_xy=True).transform
    return transform(project, pt)


@dataclass
class Bounds(BoundingBox):
    def __init__(self, left: float, bottom: float, right: float, top: float, crs: str):
        super().__init__(left, bottom, right, top, crs)

    def __repr__(self):
        return f"Bounds(left={self.left}, bottom={self.bottom}, right={self.right}, top={self.top}, crs={self.crs})"

    @classmethod
    def from_da(cls, da: xr.DataArray) -> "Bounds":
        bounds = da.odc.geobox.extent.boundingbox.bbox
        return cls(bounds[0], bounds[1], bounds[2], bounds[3], da.odc.geobox.crs)

    def as_bl_tr(self, as_crs: str = "EPSG:4326"):
        return (
            transform_point(self.left, self.bottom, self.crs, as_crs),
            transform_point(self.right, self.top, self.crs, as_crs),
        )

    def as_crs(self, as_crs):
        bl = transform_point(self.left, self.bottom, self.crs, as_crs)
        tr = transform_point(self.right, self.top, self.crs, as_crs)
        return Bounds(bl.x, bl.y, tr.x, tr.y, as_crs)
