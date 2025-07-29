FROM gitlab-registry.nrp-nautilus.io/ucsc-vizlab/spatialops/zarr-server:latest

# Install dependencies including test packages
RUN uv pip install --no-cache-dir --break-system-packages --system pytest pytest-cov pytest-asyncio

# Set environment variables for testing
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY tests/services/zarr_server/test_app.py test_app.py

# Run pytest with coverage
CMD ["pytest", "--cov=spatialoperations", "--cov-report=term-missing", "test_app.py"]
