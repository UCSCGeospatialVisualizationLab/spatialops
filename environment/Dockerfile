# Use a base image with Python
FROM mambaorg/micromamba:debian12-slim
WORKDIR /app


# Copy the setup.py and other necessary files
# Create a new environment
ARG ENVIRONMENT_FILE=environment.yml
ARG ENVIRONMENT_DIR=environment
COPY ${ENVIRONMENT_DIR} /app/${ENVIRONMENT_DIR}
USER root
RUN chmod -R 777 /app/${ENVIRONMENT_DIR}

# # Copy the installations scripts
COPY ./installations /installations
# Install pmtiles if the INSTALL_PMTILES flag is set
ARG INSTALL_PMTILES=1
RUN if [ "${INSTALL_PMTILES}" = "1" ]; then \
        echo "Installing pmtiles"; \
        bash /installations/install_pmtiles.sh; \
    else \
        echo "Not installing pmtiles"; \
    fi

# # Note that we install spatialoperations via pip in conda
RUN micromamba install -y -n base -f /app/${ENVIRONMENT_DIR}/${ENVIRONMENT_FILE} && \
micromamba clean --all --yes

# Activate the environment
SHELL ["micromamba", "run", "-n", "base", "/bin/bash", "-c"]

# Install spatialoperations via pip and pyproject.toml
COPY ./pyproject.toml /app/pyproject.toml
COPY ./spatialoperations /app/spatialoperations
COPY ./tests /app/tests
RUN pip3 install -e /app/

# Copy the notebook config file
RUN cp /app/environment/jupyter_notebook_config.py /tmp/jupyter_notebook_config.py

# Run a bash shell
CMD ["/bin/bash"]
