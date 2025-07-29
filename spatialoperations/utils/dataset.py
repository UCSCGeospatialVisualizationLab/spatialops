import logging
import os
import subprocess
import uuid

import rioxarray as rxr
import xarray as xr


def makesafe_da(da: xr.DataArray, use_micromamba=True, zeros_as_nan=True):
    id = str(uuid.uuid4())
    tmp_cog1 = f"/tmp/{id}-1.tiff"
    tmp_cog2 = f"/tmp/{id}-2.tiff"
    for p in (tmp_cog1, tmp_cog2):
        if os.path.exists(p):
            os.remove(p)
    da.rio.to_raster(tmp_cog1)
    if use_micromamba:
        mamba_cmd = "micromamba run -n base "
    else:
        mamba_cmd = ""
    bashCommand = f"{mamba_cmd}gdalwarp {tmp_cog1} {tmp_cog2} -of COG"
    logging.info(bashCommand)
    process = subprocess.Popen(bashCommand.split(" "), stdout=subprocess.PIPE)
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(line, flush=True)
    x = rxr.open_rasterio(tmp_cog2).isel(band=0)
    if zeros_as_nan:
        x = x.where(x != 0)
    os.remove(tmp_cog1)
    return x
