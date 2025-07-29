FROM ghcr.io/osgeo/gdal:ubuntu-full-latest AS builder

RUN apt update && apt install -y python3-pip python3.12-venv
RUN python3 -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN pip3 install uv

WORKDIR /app

COPY /uv.lock /app/uv.lock
RUN uv pip sync /app/uv.lock

COPY services/zarr_server/uv.lock /app/zarr_server.uv.lock
RUN uv pip install -r /app/zarr_server.uv.lock

COPY spatialoperations /app/spatialoperations
COPY pyproject.toml /app/spatialoperations/
RUN uv pip install -e ./spatialoperations

# --- Final Image ---
FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

COPY --from=builder /usr/local /usr/local
COPY --from=builder /app/spatialoperations /app/spatialoperations
COPY --from=builder /app/.venv /app/.venv
COPY services/zarr_server/app.py app/
COPY services/zarr_server/zarr_server_utils.py app/

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

# CMD ["bash"]
CMD ["python3", "app.py"]
