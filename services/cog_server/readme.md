## Purpose
To serve raster tiles from Nautilus.

### Sources
- https://cogeotiff.github.io/rio-tiler/advanced/dynamic_tiler/
- https://github.com/cogeotiff/rio-tiler
- https://cogeotiff.github.io/rio-tiler/colormap/

### TODO
- Add capacity to query a point, line, and polygon
- Add proper test case in deployment, maybe just by querying a `0/0/0.png` tile and seeing if we get a result

# Deploying the cog server

The cog_server can be deployed with:

```
make deploy-cog-server
```

This will `docker build`, `docker push`, and `helm upgrade`. The service is
accessible at `https://cog-server.nrp-nautilus.io/cogserver/`.
