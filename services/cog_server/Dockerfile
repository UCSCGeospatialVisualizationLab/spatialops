FROM ghcr.io/osgeo/gdal:ubuntu-full-latest AS builder

RUN apt update && apt install -y python3-pip
RUN pip3 install uv --break-system-packages

WORKDIR /app

COPY uv.lock /app/uv.lock

RUN uv pip install --no-cache-dir --break-system-packages --system -r /app/uv.lock

# --- Final Image ---
FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

# Copy dependencies from the builder stage
COPY --from=builder /usr/local /usr/local

WORKDIR /app

COPY app.py app.py

ENTRYPOINT ["python3", "app.py"]
