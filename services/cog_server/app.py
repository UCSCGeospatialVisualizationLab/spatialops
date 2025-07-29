import logging
import math
import os

import numpy as np
import rasterio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from rasterio.session import AWSSession
from rio_tiler.colormap import cmap
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles
from rio_tiler.utils import render

session = AWSSession(
    aws_unsigned=False,
    endpoint_url=os.environ["AWS_S3_ENDPOINT"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)


DEFAULT_SCALE = 0.1
DEFAULT_OFFSET = 10000

logging.basicConfig()
logging.root.setLevel(logging.INFO)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"],
)


def mask_zeros(data):
    """Convert greyscale to RGB for Mapbox Terrain consumption."""

    def nodata_to_zero(data, nodata):
        return 1 - (data == nodata)

    data = np.nan_to_num(data, nan=0)
    data = data * nodata_to_zero(data, 0)
    logging.info(data.shape)

    return data


def to_rgb(data, nodata, offset=1000, scale=0.1):
    """Convert greyscale to RGB for Mapbox Terrain consumption."""

    def nodata_to_zero(data, nodata):
        return 1 - (data == nodata)

    # Data Prep
    data = (data + offset) / scale
    data = data * nodata_to_zero(data, nodata)

    # RGB png band creation
    r = np.floor(data / math.pow(256, 2)) % 256
    g = np.floor(data / 256) % 256
    b = np.floor(data) % 256
    return np.array([r, g, b]).astype("uint8")


@app.get(
    r"/cogserver/{z}/{x}/{y}.png",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Return an image.",
        }
    },
    response_class=Response,
    description="Read COG and return a tile",
)
def tile(
    z: int,
    x: int,
    y: int,
    dataset: str,
    color: str = "blues",
    min_val: int = 0,
    max_val: int = 10000,
    unscale: bool = True,
    mask_min: bool = True,
    tilesize: int = 1024,
):
    """Handle tile requests."""
    path = f"{os.environ['DATA_MOUNT_PATH']}/{dataset}"
    logging.info(path)
    cm = cmap.get(color)
    # Make 0 transparent
    cm[0] = (cm[0][0], cm[0][1], cm[0][2], 0)
    options = {"unscale": unscale}
    with rasterio.Env(
        session=session,
        GDAL_DISABLE_READDIR_ON_OPEN="YES",
        AWS_VIRTUAL_HOSTING=False,
        AWS_S3_ENDPOINT=os.environ["AWS_S3_ENDPOINT"],
    ):
        with Reader(path, options=options) as dst:
            img = dst.tile(x, y, z, tilesize=tilesize)

        img.rescale(in_range=((min_val, max_val),), out_range=((0, 255),))

        content = img.render(img_format="PNG", colormap=cm, **img_profiles.get("png"))
        return Response(content, media_type="image/png")


@app.get("/cogserver/get_rgb_tile/{z}/{x}/{y}.png")
def get_rgb_tile(
    z: int,
    x: int,
    y: int,
    dataset: str,
    unscale: bool = True,
    offset: int = DEFAULT_OFFSET,
    scale: float = DEFAULT_SCALE,
):
    """Return a Mapbox-ready elevation tile."""
    options = img_profiles.get("png")
    dataset = f"{os.environ['S3_BUCKET_BASE']}/{dataset}"
    with rasterio.Env(
        session=session,
        GDAL_DISABLE_READDIR_ON_OPEN="YES",
        AWS_VIRTUAL_HOSTING=False,
        AWS_S3_ENDPOINT=os.environ["AWS_S3_ENDPOINT"],
    ):
        with Reader(dataset, options={"unscale": unscale}) as cog:
            t = cog.tile(x, y, z, tilesize=512, resampling_method="cubic")
            buff = render(
                to_rgb(t.data[0], cog.info().nodata_value, offset=offset, scale=scale),
                t.mask,  # We use dataset mask for rendering
                img_format="PNG",
                **options,
            )
            return Response(content=buff, media_type="image/png")


@app.get("/cogserver/")
def test():
    return "OK"


if __name__ == "__main__":
    uvicorn.run(
        "app:app", host="0.0.0.0", port=8080, reload=os.getenv("ENV", None) == "dev"
    )
